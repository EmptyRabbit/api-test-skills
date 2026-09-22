"""code-server 进程生命周期：启动、监听等待、闲置回收。"""

import asyncio
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path

from app.config import get_settings
from app.services import workspace
from app.windows_loop import hidden_popen_kwargs

from .extensions import ensure_debugpy, ensure_python_extensions
from .settings import (
    code_server_extensions_dir,
    code_server_user_dir,
    merge_user_python_interpreter,
    migrate_legacy_code_server_dir,
    minimal_code_server_args,
    write_minimal_user_settings,
    write_workspace_debug_config,
)
from .wsl import _wsl_launch_argv, debug_interpreter, detect_wsl_code_server


class CodeServerError(Exception):
    """code-server 拉不起来时的可展示错误。"""


def home_code_server_bins() -> list[Path]:
    home = Path.home()
    return [
        home / ".local" / "bin" / "code-server",
        home / ".local" / "code-server" / "bin" / "code-server",
    ]


def resolve_code_server_bin(bin_name: str) -> str:
    """Windows 上 CreateProcess 不吃无后缀 npm shim，必须落到 .cmd/.exe。"""
    names = [bin_name]
    if os.name == "nt" and not bin_name.lower().endswith((".cmd", ".bat", ".exe")):
        names.extend([f"{bin_name}.cmd", f"{bin_name}.bat", f"{bin_name}.exe"])
    for name in names:
        if os.path.isfile(name):
            return name
        found = shutil.which(name)
        if found:
            return found
    stem = Path(bin_name).name.lower()
    if stem in {"code-server", "code-server.cmd", "code-server.bat", "code-server.exe"}:
        for cand in home_code_server_bins():
            if cand.is_file():
                return str(cand)
    raise CodeServerError(
        f"未找到可执行文件 {bin_name}。请安装 code-server，或设置 PLATFORM_CODE_SERVER_BIN 为完整路径。"
    )


def broken_windows_npm_shim(path: str) -> bool:
    """nvm/npm 全局包只有 lib/vscode，没有 out/node/entry.js。"""
    root = Path(path).resolve().parent
    pkg = root / "node_modules" / "code-server"
    if not pkg.is_dir():
        return False
    return not (pkg / "out" / "node" / "entry.js").is_file()


def launch_argv(bin_name: str, base_args: list[str], extra_args: list[str], port: int, ws: Path) -> list[str]:
    bind = ["--bind-addr", f"127.0.0.1:{port}", *extra_args]
    if bin_name.startswith("wsl:"):
        linux_bin = bin_name[4:] or detect_wsl_code_server()
        if not linux_bin:
            raise CodeServerError("PLATFORM_CODE_SERVER_BIN=wsl: 但未在 WSL 中找到 code-server")
        return _wsl_launch_argv(linux_bin, base_args, bind, ws)

    if os.name == "nt" and bin_name == "code-server":
        wsl_bin = detect_wsl_code_server()
        native = None
        try:
            native = resolve_code_server_bin(bin_name)
        except CodeServerError:
            pass
        if wsl_bin and (native is None or broken_windows_npm_shim(native)):
            return _wsl_launch_argv(wsl_bin, base_args, bind, ws)
        if native:
            return [native, *base_args, *bind, str(ws)]
        raise CodeServerError(
            "未找到可用的 code-server。Windows npm 全局包不完整；请在 WSL 安装到 ~/.local/code-server，"
            "或设置 PLATFORM_CODE_SERVER_BIN。"
        )

    return [resolve_code_server_bin(bin_name), *base_args, *bind, str(ws)]


class _Proc:
    """subprocess.Popen wrapper; asyncio.create_subprocess_exec fails on Windows SelectorEventLoop."""

    def __init__(self, popen: subprocess.Popen, log_file=None):
        self._p = popen
        self._log_file = log_file

    @property
    def returncode(self) -> int | None:
        return self._p.poll()

    def terminate(self) -> None:
        self._p.terminate()

    def kill(self) -> None:
        self._p.kill()

    def close_log(self) -> None:
        if self._log_file is None:
            return
        try:
            self._log_file.close()
        except OSError:
            pass
        self._log_file = None

    async def wait(self) -> int:
        return await asyncio.to_thread(self._p.wait)


class _Instance:
    def __init__(self, proc: _Proc, port: int, via_wsl: bool = False, interpreter: str = ""):
        self.proc = proc
        self.port = port
        self.via_wsl = via_wsl
        self.interpreter = interpreter
        self.last_active = time.time()


def _read_tail(path: Path, limit: int = 1200) -> str:
    try:
        with path.open("rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - limit))
            return f.read().decode("utf-8", "replace").strip()
    except OSError:
        return ""


class CodeServerManager:
    def __init__(
        self,
        bin: str | None = None,
        base_args: list[str] | None = None,
        extra_args: list[str] | None = None,
    ):
        settings = get_settings()
        self.bin = bin or settings.code_server_bin
        self.base_args = base_args or []
        # extra_args is None → 精简离线参数；测试传 [] 避免给 python dummy 加未知 flag
        self.extra_args = extra_args
        self.idle_seconds = settings.code_server_idle_minutes * 60
        self.instances: dict[str, _Instance] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _maybe_install_python_extensions(self, via_wsl: bool) -> None:
        if self.extra_args is not None:
            return
        data_dir = get_settings().data_dir
        migrate_legacy_code_server_dir(data_dir)
        user_dir = code_server_user_dir(data_dir)
        write_minimal_user_settings(user_dir)
        merge_user_python_interpreter(user_dir, debug_interpreter(via_wsl=via_wsl))
        ensure_python_extensions(code_server_extensions_dir(data_dir), via_wsl=via_wsl)
        ensure_debugpy()

    def _free_port(self) -> int:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    async def ensure(self, session_id: str, *, wait_port: bool = True) -> int:
        lock = self._locks.setdefault(session_id, asyncio.Lock())
        async with lock:
            return await self._ensure_locked(session_id, wait_port=wait_port)

    async def _ensure_locked(self, session_id: str, *, wait_port: bool) -> int:
        inst = self.instances.get(session_id)
        if inst and inst.proc.returncode is None:
            interpreter = debug_interpreter(via_wsl=inst.via_wsl)
            if inst.interpreter == interpreter:
                inst.last_active = time.time()
                return inst.port
            await self.shutdown(session_id)
        elif inst:
            inst.proc.close_log()
            self.instances.pop(session_id, None)

        port = self._free_port()
        ws = workspace.workspace_root(session_id)
        ws.mkdir(parents=True, exist_ok=True)
        log_path = ws / ".code-server.log"
        extra = self.extra_args
        if extra is None:
            extra = minimal_code_server_args(get_settings().data_dir)
        args = launch_argv(self.bin, self.base_args, extra, port, ws)
        via_wsl = bool(args) and Path(args[0]).name.lower() == "wsl.exe"
        interpreter = debug_interpreter(via_wsl=via_wsl)
        write_workspace_debug_config(ws, interpreter)
        self._maybe_install_python_extensions(via_wsl)

        def _spawn() -> _Proc:
            log_file = open(log_path, "wb")
            try:
                return _Proc(
                    subprocess.Popen(
                        args,
                        stdout=log_file,
                        stderr=subprocess.STDOUT,
                        **hidden_popen_kwargs(),
                    ),
                    log_file,
                )
            except OSError as e:
                log_file.close()
                raise CodeServerError(f"无法启动 {args[0]}：{e}") from e

        proc = await asyncio.to_thread(_spawn)
        if wait_port:
            await self._wait_listening(proc, port, log_path)
        self.instances[session_id] = _Instance(
            proc, port, via_wsl=via_wsl, interpreter=interpreter
        )
        return port

    async def _wait_listening(self, proc: _Proc, port: int, log_path: Path) -> None:
        for _ in range(60):
            if proc.returncode is not None:
                proc.close_log()
                detail = _read_tail(log_path) or f"exit {proc.returncode}"
                if "Cannot find module" in detail and "code-server" in detail:
                    raise CodeServerError(
                        "Windows 上的 npm code-server 不完整。已优先使用 WSL ~/.local/code-server；"
                        "若仍看到此错误，请重启后端后再打开 VS Code 页签。"
                    )
                raise CodeServerError(
                    f"code-server 启动失败（exit {proc.returncode}）。{detail}"
                )
            try:
                reader, writer = await asyncio.open_connection("127.0.0.1", port)
                writer.close()
                await writer.wait_closed()
                return
            except OSError:
                await asyncio.sleep(0.5)
        proc.terminate()
        proc.close_log()
        raise CodeServerError("code-server 在 30s 内未监听端口，请查看工作区 .code-server.log")

    async def shutdown(self, session_id: str) -> None:
        inst = self.instances.pop(session_id, None)
        if inst is None:
            return
        if inst.proc.returncode is None:
            inst.proc.terminate()
            try:
                await asyncio.wait_for(inst.proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                inst.proc.kill()
        inst.proc.close_log()

    async def sweep(self) -> None:
        now = time.time()
        idle = [sid for sid, inst in self.instances.items() if now - inst.last_active > self.idle_seconds]
        for sid in idle:
            await self.shutdown(sid)


manager = CodeServerManager()

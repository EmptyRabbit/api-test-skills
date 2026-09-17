import asyncio
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath

from app.config import get_settings
from app.services import workspace
from app.windows_loop import hidden_popen_kwargs


class CodeServerError(Exception):
    """code-server 拉不起来时的可展示错误。"""


# 只保留本机编辑/调试：关掉更新、遥测、欢迎页、端口转发代理。
MINIMAL_CODE_SERVER_FLAGS = [
    "--auth",
    "none",
    "--disable-update-check",
    "--disable-telemetry",
    "--disable-getting-started-override",
    "--disable-workspace-trust",
    "--disable-proxy",
]

DARK_WORKBENCH_SETTINGS = {
    "workbench.colorTheme": "Default Dark Modern",
    "workbench.preferredDarkColorTheme": "Default Dark Modern",
    "window.autoDetectColorScheme": False,
}

MINIMAL_USER_SETTINGS = {
    "telemetry.telemetryLevel": "off",
    "workbench.enableExperiments": False,
    "workbench.startupEditor": "none",
    "workbench.tips.enabled": False,
    "workbench.welcomePage.walkthroughs.hideOnStartup": True,
    "workbench.layoutControl.enabled": False,
    "window.menuBarVisibility": "compact",
    "extensions.autoUpdate": False,
    "extensions.autoCheckUpdates": False,
    "extensions.ignoreRecommendations": True,
    "update.mode": "none",
    "git.autofetch": False,
    "npm.fetchOnlinePackageInfo": False,
    "typescript.disableAutomaticTypeAcquisition": True,
    "editor.minimap.enabled": False,
    "breadcrumbs.enabled": False,
    "workbench.editor.enablePreview": False,
    "security.workspace.trust.enabled": False,
    "debug.toolBarLocation": "docked",
    "debug.openDebug": "openOnDebugBreak",
    **DARK_WORKBENCH_SETTINGS,
}


def _load_json(path: Path):
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _dump_json(path: Path, data, *, indent: int | str = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=indent), encoding="utf-8")


def code_server_root(data_dir: Path) -> Path:
    return data_dir / "code-server"


def code_server_user_dir(data_dir: Path) -> Path:
    return code_server_root(data_dir) / "user"


def code_server_extensions_dir(data_dir: Path) -> Path:
    return code_server_root(data_dir) / "extensions"


def migrate_legacy_code_server_dir(data_dir: Path) -> None:
    """把旧的 data/code-server-user 收口到 data/code-server/{user,extensions}。"""
    old = data_dir / "code-server-user"
    if not old.exists():
        return
    root = code_server_root(data_dir)
    user = code_server_user_dir(data_dir)
    ext = code_server_extensions_dir(data_dir)
    if user.exists() or ext.exists():
        return
    root.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(str(old), str(user))
    except OSError:
        return
    nested_ext = user / "extensions"
    if nested_ext.exists() and not ext.exists():
        shutil.move(str(nested_ext), str(ext))
    nested_cache = user / "vsix-cache"
    if nested_cache.exists():
        shutil.move(str(nested_cache), str(root / "vsix-cache"))


def write_minimal_user_settings(user_dir: Path) -> None:
    user_dir.mkdir(parents=True, exist_ok=True)
    settings = user_dir / "User" / "settings.json"
    loaded = _load_json(settings)
    existing = loaded if isinstance(loaded, dict) else None
    if existing and all(existing.get(k) == v for k, v in DARK_WORKBENCH_SETTINGS.items()):
        return
    _dump_json(settings, {**(existing or MINIMAL_USER_SETTINGS), **DARK_WORKBENCH_SETTINGS})


def minimal_code_server_args(data_dir: Path) -> list[str]:
    migrate_legacy_code_server_dir(data_dir)
    user = code_server_user_dir(data_dir)
    ext = code_server_extensions_dir(data_dir)
    write_minimal_user_settings(user)
    ext.mkdir(parents=True, exist_ok=True)
    return [
        *MINIMAL_CODE_SERVER_FLAGS,
        "--user-data-dir",
        str(user),
        "--extensions-dir",
        str(ext),
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


def win_to_wsl_path(path: Path) -> str:
    win = str(path.resolve())
    try:
        r = subprocess.run(
            ["wsl.exe", "wslpath", "-a", win],
            capture_output=True,
            text=True,
            timeout=8,
            **hidden_popen_kwargs(),
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    if len(win) >= 2 and win[1] == ":":
        return "/mnt/" + win[0].lower() + win[2:].replace("\\", "/")
    return win.replace("\\", "/")


_WSL_DETECT = (
    "for p in "
    '"$HOME/.local/code-server/bin/code-server" '
    "/usr/bin/code-server "
    "/usr/lib/code-server/bin/code-server; "
    "do [ -x \"$p\" ] && echo \"$p\" && exit 0; done; exit 1"
)

_wsl_bin_cache: str | None | bool = False
_wsl_pytest_py_cache: str | None | bool = False


def _wsl_bash_first_match(script: str) -> str | None:
    try:
        r = subprocess.run(
            ["wsl.exe", "--exec", "/bin/bash", "--noprofile", "--norc", "-c", script],
            capture_output=True,
            text=True,
            timeout=12,
            **hidden_popen_kwargs(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    line = (r.stdout or "").strip().splitlines()
    return line[-1] if line else None


def detect_wsl_code_server() -> str | None:
    global _wsl_bin_cache
    if _wsl_bin_cache is not False:
        return _wsl_bin_cache  # type: ignore[return-value]
    _wsl_bin_cache = _wsl_bash_first_match(_WSL_DETECT)
    return _wsl_bin_cache


_WSL_PYTEST_DETECT = (
    "for p in "
    '"$HOME/.venvs/api-test-artifacts/bin/python3" '
    '"$HOME/.local/share/api-test-skills/venv/bin/python3"; '
    "do [ -x \"$p\" ] && echo \"$p\" && exit 0; done; exit 1"
)


def detect_wsl_pytest_python() -> str | None:
    """WSL code-server 不能跑 Windows .venv\\Scripts\\python.exe，需 Linux 解释器。"""
    global _wsl_pytest_py_cache
    if _wsl_pytest_py_cache is not False:
        return _wsl_pytest_py_cache  # type: ignore[return-value]
    _wsl_pytest_py_cache = _wsl_bash_first_match(_WSL_PYTEST_DETECT)
    return _wsl_pytest_py_cache


_WSL_PATH_FLAGS = {"--user-data-dir", "--extensions-dir"}


def wslify_args(args: list[str]) -> list[str]:
    """把传给 Linux code-server 的 Windows 路径参数改成 /mnt/…。"""
    out: list[str] = []
    convert_next = False
    for a in args:
        if convert_next:
            out.append(win_to_wsl_path(Path(a)))
            convert_next = False
            continue
        out.append(a)
        convert_next = a in _WSL_PATH_FLAGS
    return out


def _wsl_launch_argv(linux_bin: str, base_args: list[str], bind: list[str], ws: Path) -> list[str]:
    return [
        "wsl.exe",
        "--exec",
        linux_bin,
        *wslify_args(base_args),
        *wslify_args(bind),
        win_to_wsl_path(ws),
    ]


def debug_interpreter(*, via_wsl: bool) -> str:
    """给内嵌 VS Code 写解释器。WSL 侧必须用 Linux python，不能用 Windows .exe。"""
    py = Path(sys.executable)
    if not via_wsl:
        return str(py.resolve())
    return detect_wsl_pytest_python() or win_to_wsl_path(py)


def python_tool_paths(interpreter: str) -> dict[str, str]:
    """venv 根目录与 pytest 可执行文件，供扩展自动发现而不用手选解释器。"""
    win_drive = len(interpreter) >= 2 and interpreter[1] == ":"
    p = PureWindowsPath(interpreter) if win_drive else PurePosixPath(interpreter.replace("\\", "/"))
    if p.parent.name not in {"bin", "Scripts"}:
        return {}
    pytest_name = "pytest.exe" if p.suffix.lower() == ".exe" else "pytest"
    return {
        "python.venvPath": str(p.parent.parent.parent),
        "python.testing.pytestPath": str(p.parent / pytest_name),
    }


def merge_user_python_interpreter(user_dir: Path, interpreter: str) -> None:
    path = user_dir / "User" / "settings.json"
    loaded = _load_json(path)
    data = loaded if isinstance(loaded, dict) else {}
    if data.get("python.defaultInterpreterPath") == interpreter:
        return
    data["python.defaultInterpreterPath"] = interpreter
    data["python.createEnvironment.trigger"] = "off"
    _dump_json(path, data)


def write_workspace_debug_config(ws: Path, interpreter: str) -> None:
    vscode_dir = ws / ".vscode"
    vscode_dir.mkdir(parents=True, exist_ok=True)
    artifacts = "${workspaceFolder}/artifacts"
    settings = {
        "python.defaultInterpreterPath": interpreter,
        "python.languageServer": "Jedi",
        "python.terminal.activateEnvironment": True,
        "python.testing.pytestEnabled": True,
        "python.testing.unittestEnabled": False,
        "python.testing.cwd": artifacts,
        "python.testing.pytestArgs": ["."],
        "python.analysis.extraPaths": [artifacts],
        "python.createEnvironment.trigger": "off",
        **python_tool_paths(interpreter),
    }
    (vscode_dir / "settings.json").write_text(
        json.dumps(settings, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    debugpy = {
        "type": "debugpy",
        "request": "launch",
        "python": interpreter,
        "console": "integratedTerminal",
        "env": {"PYTHONPATH": artifacts},
    }
    launch = {
        "version": "0.2.0",
        "configurations": [
            {
                **debugpy,
                "name": "pytest (artifacts)",
                "module": "pytest",
                "args": ["-sv", "."],
                "cwd": artifacts,
                "justMyCode": False,
            },
            {
                **debugpy,
                "name": "Python: Current File",
                "program": "${file}",
                "cwd": "${fileDirname}",
            },
            {
                **debugpy,
                "name": "Debug Test",
                "purpose": ["debug-test"],
                "cwd": artifacts,
                "justMyCode": False,
            },
        ],
    }
    (vscode_dir / "launch.json").write_text(
        json.dumps(launch, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def python_extension_installed(extensions_dir: Path) -> bool:
    return _python_extension_dir(extensions_dir) is not None


def extract_vsix(vsix: Path, extensions_dir: Path) -> Path:
    extensions_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(vsix) as z:
        pkg = json.loads(z.read("extension/package.json"))
        folder = f"{pkg['publisher']}.{pkg['name']}-{pkg['version']}"
        dest = extensions_dir / folder
        if dest.is_dir():
            return dest
        tmp = extensions_dir / (folder + ".tmp")
        shutil.rmtree(tmp, ignore_errors=True)
        for info in z.infolist():
            name = info.filename.replace("\\", "/")
            if not name.startswith("extension/") or name in {"extension/", "extension"}:
                continue
            rel = name[len("extension/") :]
            target = tmp / rel
            if info.is_dir() or name.endswith("/"):
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, target.open("wb") as out:
                shutil.copyfileobj(src, out)
    tmp.rename(dest)
    return dest


def _open_vsx_download_url(publisher: str, name: str, target: str | None) -> str:
    if target:
        api = f"https://open-vsx.org/api/{publisher}/{name}/{target}/latest"
    else:
        api = f"https://open-vsx.org/api/{publisher}/{name}/latest"
    with urllib.request.urlopen(api, timeout=30) as resp:
        data = json.load(resp)
    url = (data.get("files") or {}).get("download")
    if not url:
        raise RuntimeError(f"Open VSX 未返回 {publisher}.{name} 的 VSIX")
    return url


def _download_url(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as resp, dest.open("wb") as f:
        shutil.copyfileobj(resp, f)


def _install_open_vsx_extension(
    publisher: str,
    name: str,
    extensions_dir: Path,
    *,
    target: str | None,
    cache_dir: Path,
) -> None:
    vsix = cache_dir / f"{publisher}.{name}.vsix"
    url = _open_vsx_download_url(publisher, name, target)
    _download_url(url, vsix)
    extract_vsix(vsix, extensions_dir)


def _python_extension_dir(extensions_dir: Path) -> Path | None:
    if not extensions_dir.is_dir():
        return None
    found = [p for p in extensions_dir.iterdir() if p.is_dir() and p.name.startswith("ms-python.python-")]
    return max(found, key=lambda p: p.name) if found else None


def _remove_obsolete_entries(extensions_dir: Path, needle: str) -> None:
    obsolete = extensions_dir / ".obsolete"
    if not obsolete.is_file():
        return
    try:
        data = json.loads(obsolete.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    if not isinstance(data, dict):
        return
    keys = [k for k in data if needle in k.lower()]
    if not keys:
        return
    for k in keys:
        data.pop(k, None)
    if data:
        obsolete.write_text(json.dumps(data), encoding="utf-8")
    else:
        obsolete.unlink(missing_ok=True)


def _drop_magicpython(extensions_dir: Path) -> None:
    if not extensions_dir.is_dir():
        return
    for p in extensions_dir.iterdir():
        if p.is_dir() and p.name.startswith("magicstack.MagicPython-"):
            shutil.rmtree(p, ignore_errors=True)
    _remove_obsolete_entries(extensions_dir, "magicpython")


def _invalidate_user_extension_cache(user_dir: Path) -> None:
    cached = user_dir / "CachedProfilesData"
    if not cached.is_dir():
        return
    for p in cached.rglob("extensions.user.cache"):
        p.unlink(missing_ok=True)


def _strip_injected_python_grammar(extensions_dir: Path) -> None:
    """撤销早前塞进 ms-python.python 的 python 语言/语法贡献。

    code-server 自带内置扩展 vscode.python（lib/vscode/extensions/python，随
    code-server 安装自带，始终生效），本来就贡献了 language id "python" 和
    scopeName "source.python" 的 MagicPython 语法。之前往 ms-python.python 里
    注入同样的 language id / scopeName 纯属重复注册，两边打架反而谁都渲染不出
    颜色，所以这里清掉注入的部分，只留内置的那份生效。
    """
    py = _python_extension_dir(extensions_dir)
    if py is None:
        return
    pkg_path = py / "package.json"
    if not pkg_path.is_file():
        return
    try:
        pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    if not isinstance(pkg, dict):
        return
    contributes = pkg.get("contributes") or {}
    langs = contributes.get("languages") or []
    grammars = contributes.get("grammars") or []
    new_langs = [lang for lang in langs if lang.get("id") != "python"]
    new_grammars = [g for g in grammars if g.get("scopeName") != "source.python"]
    if len(new_langs) == len(langs) and len(new_grammars) == len(grammars):
        return  # 没注入过，不用动
    contributes["languages"] = new_langs
    contributes["grammars"] = new_grammars
    pkg["contributes"] = contributes
    pkg_path.write_text(json.dumps(pkg, ensure_ascii=False, indent="\t") + "\n", encoding="utf-8")
    (py / "syntaxes" / "python.tmLanguage.json").unlink(missing_ok=True)
    _invalidate_user_extension_cache(extensions_dir.parent / "user")


def _remove_ui_python_syntax_extension(extensions_dir: Path) -> None:
    """删掉之前手搓的 platform.python-syntax UI 扩展及其登记，同样是为了不跟内置扩展抢注。"""
    dest = extensions_dir / "platform.python-syntax-1.0.0"
    if dest.is_dir():
        shutil.rmtree(dest, ignore_errors=True)
    manifest_path = extensions_dir / "extensions.json"
    if manifest_path.is_file():
        try:
            entries = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            entries = None
        if isinstance(entries, list):
            filtered = [e for e in entries if (e.get("identifier") or {}).get("id") != "platform.python-syntax"]
            if len(filtered) != len(entries):
                manifest_path.write_text(json.dumps(filtered), encoding="utf-8")
    _remove_obsolete_entries(extensions_dir, "platform.python-syntax")
    _invalidate_user_extension_cache(extensions_dir.parent / "user")


def ensure_python_extensions(extensions_dir: Path, *, via_wsl: bool = False) -> None:
    extensions_dir.mkdir(parents=True, exist_ok=True)
    cache = extensions_dir.parent / "vsix-cache"
    debugpy_target = "linux-x64" if via_wsl or os.name != "nt" else "win32-x64"
    try:
        if not python_extension_installed(extensions_dir):
            _install_open_vsx_extension(
                "ms-python", "python", extensions_dir, target=None, cache_dir=cache
            )
            _install_open_vsx_extension(
                "ms-python",
                "debugpy",
                extensions_dir,
                target=debugpy_target,
                cache_dir=cache,
            )
        _strip_injected_python_grammar(extensions_dir)
        _remove_ui_python_syntax_extension(extensions_dir)
        _drop_magicpython(extensions_dir)
    except (OSError, RuntimeError, urllib.error.URLError, TimeoutError, zipfile.BadZipFile):
        return


def ensure_debugpy() -> None:
    try:
        import debugpy  # noqa: F401
        return
    except ImportError:
        pass
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "debugpy"],
            capture_output=True,
            timeout=120,
            **hidden_popen_kwargs(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return


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

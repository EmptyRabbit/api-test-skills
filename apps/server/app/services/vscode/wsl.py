"""Windows → WSL 的路径与启动翻译。"""

import subprocess
import sys
from pathlib import Path

from app.windows_loop import hidden_popen_kwargs


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


# Windows 会把 HOME 泄漏进 WSL（例如 D:Users…），探测必须改用 passwd 里的 Linux 家目录。
_WSL_FIX_HOME = (
    'h=$(getent passwd "$(id -un)" | cut -d: -f6); '
    '[ -n "$h" ] && export HOME="$h"; '
)

_WSL_DETECT = (
    "for p in "
    '"$HOME/.local/bin/code-server" '
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
            ["wsl.exe", "--exec", "/bin/bash", "--noprofile", "--norc", "-c", _WSL_FIX_HOME + script],
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

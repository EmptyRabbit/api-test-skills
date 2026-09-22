"""code-server 集成：进程 / 扩展 / 配置物化 / WSL 四个内部模块的对外门面。

对外接口保持与旧单文件 vscode.py 一致；测试通过 vscode.os / vscode.subprocess /
vscode.sys / vscode.manager 打桩，故这里显式 import 这三个全局模块。
"""

import os  # noqa: F401 —— 测试会 patch vscode.os
import shutil  # noqa: F401 —— 测试会 patch vscode.shutil
import subprocess  # noqa: F401 —— 测试会 patch vscode.subprocess
import sys  # noqa: F401 —— 测试会 patch vscode.sys
from pathlib import Path  # noqa: F401 —— 测试会 patch vscode.Path

from .extensions import (
    _install_open_vsx_extension,
    _open_vsx_download_url,
    ensure_debugpy,
    ensure_python_extensions,
    extract_vsix,
    python_extension_installed,
)
from .process import (
    CodeServerManager,
    CodeServerError,
    broken_windows_npm_shim,
    home_code_server_bins,
    launch_argv,
    manager,
    resolve_code_server_bin,
)
from .settings import (
    DARK_WORKBENCH_SETTINGS,
    MINIMAL_CODE_SERVER_FLAGS,
    MINIMAL_USER_SETTINGS,
    code_server_extensions_dir,
    code_server_root,
    code_server_user_dir,
    merge_user_python_interpreter,
    migrate_legacy_code_server_dir,
    minimal_code_server_args,
    python_tool_paths,
    write_minimal_user_settings,
    write_workspace_debug_config,
)
from .wsl import (
    _WSL_DETECT,
    _wsl_bash_first_match,
    debug_interpreter,
    detect_wsl_code_server,
    detect_wsl_pytest_python,
    win_to_wsl_path,
    wslify_args,
)

__all__ = [
    "CodeServerManager",
    "CodeServerError",
    "broken_windows_npm_shim",
    "code_server_extensions_dir",
    "code_server_root",
    "code_server_user_dir",
    "dark_workbench_settings",
    "debug_interpreter",
    "detect_wsl_code_server",
    "detect_wsl_pytest_python",
    "ensure_debugpy",
    "ensure_python_extensions",
    "extract_vsix",
    "home_code_server_bins",
    "launch_argv",
    "manager",
    "merge_user_python_interpreter",
    "migrate_legacy_code_server_dir",
    "minimal_code_server_args",
    "python_extension_installed",
    "python_tool_paths",
    "resolve_code_server_bin",
    "win_to_wsl_path",
    "wslify_args",
]

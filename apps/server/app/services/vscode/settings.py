"""code-server 用户设置与工作区调试配置物化。"""

import json
import shutil
from pathlib import Path, PurePosixPath, PureWindowsPath


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

import asyncio
import json
from pathlib import Path

import pytest

from app.services import vscode


@pytest.fixture
def mgr(settings, monkeypatch):
    monkeypatch.setattr("app.services.workspace._data_dir", settings.data_dir)
    # extra_args=[] skips MINIMAL_CODE_SERVER_FLAGS so the python dummy is not given unknown flags.
    return vscode.CodeServerManager(
        bin="python",
        base_args=["-c", "import time; time.sleep(999)"],
        extra_args=[],
    )


def _seed_session(settings, monkeypatch, sid: str) -> None:
    from app import db as db_mod
    from app.db import SessionRow

    monkeypatch.setattr("app.services.workspace._data_dir", settings.data_dir)
    db_mod.init_engine(settings.database_url, settings.data_dir)
    with db_mod.SessionLocal() as s:
        s.add(
            SessionRow(
                id=sid,
                user_name="u",
                git_url="x",
                base_branch="m",
                feature_branch="f",
                status="ready",
            )
        )
        s.commit()


def _proxy_client(settings, monkeypatch, sid: str, handler):
    import httpx
    from fastapi.testclient import TestClient

    from app.main import build_app

    _seed_session(settings, monkeypatch, sid)
    monkeypatch.setattr(
        "app.routers.vscode._client",
        lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    monkeypatch.setattr(vscode.manager, "ensure", lambda _sid: asyncio.sleep(0, result=8765))
    return TestClient(build_app(settings))


async def test_ensure_spawns_and_reuses(mgr, settings):
    from app.services import workspace

    ws = workspace.workspace_root("s-vs")
    ws.mkdir(parents=True, exist_ok=True)
    port1 = await mgr.ensure("s-vs", wait_port=False)
    assert port1 > 0
    port2 = await mgr.ensure("s-vs", wait_port=False)
    assert port1 == port2
    await mgr.shutdown("s-vs")


async def test_ensure_serializes_concurrent_spawns(mgr, settings):
    from app.services import workspace

    workspace.workspace_root("s-vs-lock").mkdir(parents=True, exist_ok=True)
    p1, p2 = await asyncio.gather(
        mgr.ensure("s-vs-lock", wait_port=False),
        mgr.ensure("s-vs-lock", wait_port=False),
    )
    assert p1 == p2
    assert len(mgr.instances) == 1
    await mgr.shutdown("s-vs-lock")


def test_win_to_wsl_path_fallback(monkeypatch):
    def _no_wsl(*_a, **_k):
        raise OSError("no wsl")

    monkeypatch.setattr(vscode.subprocess, "run", _no_wsl)
    got = vscode.win_to_wsl_path(Path(r"D:\workgit\api-test-skills"))
    assert got == "/mnt/d/workgit/api-test-skills"


def test_launch_argv_prefers_wsl_when_windows_shim_broken(monkeypatch, tmp_path):
    monkeypatch.setattr(vscode, "detect_wsl_code_server", lambda: "/home/u/.local/code-server/bin/code-server")
    monkeypatch.setattr(vscode, "resolve_code_server_bin", lambda _n: str(tmp_path / "code-server.cmd"))
    monkeypatch.setattr(vscode, "broken_windows_npm_shim", lambda _p: True)
    monkeypatch.setattr(vscode, "win_to_wsl_path", lambda p: "/mnt/d/ws")
    monkeypatch.setattr(vscode.os, "name", "nt")
    argv = vscode.launch_argv("code-server", [], ["--auth", "none"], 9876, tmp_path)
    assert argv[0] == "wsl.exe"
    assert argv[2] == "/home/u/.local/code-server/bin/code-server"
    assert "127.0.0.1:9876" in argv
    assert argv[-1] == "/mnt/d/ws"


def test_launch_argv_python_stays_native():
    argv = vscode.launch_argv("python", ["-c", "import time; time.sleep(999)"], [], 1, Path("."))
    assert "python" in argv[0].lower()


def test_resolve_bin_missing():
    with pytest.raises(vscode.CodeServerError, match="未找到"):
        vscode.resolve_code_server_bin("definitely-not-a-code-server-bin")


async def test_ensure_missing_bin(settings, monkeypatch):
    monkeypatch.setattr("app.services.workspace._data_dir", settings.data_dir)
    mgr = vscode.CodeServerManager(bin="definitely-not-a-code-server-bin", extra_args=[])
    with pytest.raises(vscode.CodeServerError, match="未找到"):
        await mgr.ensure("s-missing")


async def test_ensure_exited_process(settings, monkeypatch):
    monkeypatch.setattr("app.services.workspace._data_dir", settings.data_dir)
    mgr = vscode.CodeServerManager(
        bin="python",
        base_args=["-c", "raise SystemExit(2)"],
        extra_args=[],
    )
    with pytest.raises(vscode.CodeServerError, match="启动失败"):
        await mgr.ensure("s-dead")


def test_ensure_endpoint_maps_error(settings, monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import build_app

    _seed_session(settings, monkeypatch, "s-vs-err")

    async def boom(_sid: str, **_kw):
        raise vscode.CodeServerError("boom-detail")

    monkeypatch.setattr(vscode.manager, "ensure", boom)
    resp = TestClient(build_app(settings)).post("/api/sessions/s-vs-err/vscode/ensure")
    assert resp.status_code == 503
    assert resp.json()["detail"] == "boom-detail"


async def test_sweep_kills_idle(mgr, monkeypatch):
    from app.services import workspace

    ws = workspace.workspace_root("s-vs2")
    ws.mkdir(parents=True, exist_ok=True)
    await mgr.ensure("s-vs2", wait_port=False)
    inst = mgr.instances["s-vs2"]
    inst.last_active = 0.0  # pretend it was idle a long time ago
    await mgr.sweep()
    assert "s-vs2" not in mgr.instances


def test_rewrite_workbench_html_sets_session_prefix():
    from app.routers.vscode import rewrite_workbench_html, vscode_public_prefix

    prefix = vscode_public_prefix("s-any")
    html = (
        '<meta data-settings="{&quot;remoteAuthority&quot;:&quot;remote&quot;,'
        '&quot;serverBasePath&quot;:&quot;/&quot;,'
        '&quot;webviewEndpoint&quot;:&quot;./stable-b7ef8f9bd70cb5b342fa8ec8a0086bad676d8124/static/out/vs/workbench/contrib/webview/browser/pre&quot;,'
        '&quot;enableTelemetry&quot;:true,'
        '&quot;productConfiguration&quot;:{&quot;codeServerVersion&quot;:&quot;4.96.4&quot;},'
        '&quot;telemetryEndpoint&quot;:&quot;https://v1.telemetry.coder.com/track&quot;,'
        '&quot;extensionsGallery&quot;:{&quot;serviceUrl&quot;:&quot;https://open-vsx.org/vscode/gallery&quot;}}">'
    )
    out = rewrite_workbench_html(html, prefix)
    assert "&quot;serverBasePath&quot;:&quot;/api/sessions/s-any/vscode&quot;" in out
    assert "&quot;serverBasePath&quot;:&quot;/&quot;" not in out
    assert "&quot;enableTelemetry&quot;:false" in out
    assert "&quot;quality&quot;:&quot;stable&quot;" in out
    assert "&quot;commit&quot;:&quot;b7ef8f9bd70cb5b342fa8ec8a0086bad676d8124&quot;" in out
    assert "open-vsx.org" not in out
    assert "telemetry.coder.com" not in out


def test_remap_builtin_extension_cdn_query_to_static():
    from app.routers import vscode as vscode_router

    vscode_router._workbench_commits.clear()
    vscode_router.remember_workbench_commit(
        "/api/sessions/s-any/vscode",
        "stable-b7ef8f9bd70cb5b342fa8ec8a0086bad676d8124/static",
    )
    path, query = vscode_router.remap_vscode_asset_request(
        "s-any",
        "",
        "vscode-cdn.net/extensions/python/syntaxes/MagicPython.tmLanguage.json",
    )
    assert path == (
        "stable-b7ef8f9bd70cb5b342fa8ec8a0086bad676d8124/static/extensions/"
        "python/syntaxes/MagicPython.tmLanguage.json"
    )
    assert query == ""


def test_remap_collapses_doubled_remote_resource_path():
    from app.routers import vscode as vscode_router

    vscode_router._workbench_commits.clear()
    path, query = vscode_router.remap_vscode_asset_request(
        "s-any",
        "api/sessions/s-any/vscode/"
        "stable-b7ef8f9bd70cb5b342fa8ec8a0086bad676d8124/vscode-remote-resource",
        "path=%2Fhome%2Fu%2Fextensions%2Fpython%2Fsyntaxes%2FMagicPython.tmLanguage.json",
    )
    assert path == "vscode-remote-resource"
    assert "MagicPython" in query


def test_remap_builtin_extension_ignores_normal_query():
    from app.routers import vscode as vscode_router

    vscode_router._workbench_commits.clear()
    vscode_router.remember_workbench_commit(
        "/api/sessions/s-any/vscode",
        "stable-b7ef8f9bd70cb5b342fa8ec8a0086bad676d8124/static",
    )
    path, query = vscode_router.remap_vscode_asset_request(
        "s-any", "", "folder=/mnt/d/ws"
    )
    assert path == ""
    assert query == "folder=/mnt/d/ws"


def test_minimal_code_server_args_offline_and_local_ui(tmp_path):
    args = vscode.minimal_code_server_args(tmp_path)
    assert "--disable-telemetry" in args
    assert "--disable-proxy" in args
    assert "--user-data-dir" in args
    user = tmp_path / "code-server" / "user"
    ext = tmp_path / "code-server" / "extensions"
    settings = user / "User" / "settings.json"
    assert settings.is_file()
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["telemetry.telemetryLevel"] == "off"
    assert data["workbench.colorTheme"] == "Default Dark Modern"
    joined = " ".join(args)
    assert str(user) in joined
    assert str(ext) in joined
    assert ext.is_dir()


def test_migrate_legacy_code_server_dir(tmp_path):
    old = tmp_path / "code-server-user"
    (old / "User").mkdir(parents=True)
    (old / "User" / "settings.json").write_text("{}", encoding="utf-8")
    (old / "extensions" / "ms-python.python-1.0.0").mkdir(parents=True)
    (old / "vsix-cache").mkdir()
    (old / "vsix-cache" / "ms-python.python.vsix").write_text("x", encoding="utf-8")
    vscode.migrate_legacy_code_server_dir(tmp_path)
    assert not old.exists()
    assert (tmp_path / "code-server" / "user" / "User" / "settings.json").is_file()
    assert (tmp_path / "code-server" / "extensions" / "ms-python.python-1.0.0").is_dir()
    assert (tmp_path / "code-server" / "vsix-cache" / "ms-python.python.vsix").is_file()
    vscode.migrate_legacy_code_server_dir(tmp_path)  # 幂等


def test_write_minimal_user_settings_forces_dark_theme(tmp_path):
    user = tmp_path / "code-server" / "user"
    (user / "User").mkdir(parents=True)
    (user / "User" / "settings.json").write_text(
        json.dumps({"telemetry.telemetryLevel": "off", "workbench.colorTheme": "Default Light+"}),
        encoding="utf-8",
    )
    vscode.write_minimal_user_settings(user)
    data = json.loads((user / "User" / "settings.json").read_text(encoding="utf-8"))
    assert data["telemetry.telemetryLevel"] == "off"
    assert data["workbench.colorTheme"] == "Default Dark Modern"
    assert data["window.autoDetectColorScheme"] is False


def test_wslify_args_converts_user_and_ext_dirs(monkeypatch, tmp_path):
    monkeypatch.setattr(vscode, "win_to_wsl_path", lambda p: "/mnt/d/" + Path(p).name)
    args = ["--auth", "none", "--user-data-dir", str(tmp_path / "ud"), "--extensions-dir", str(tmp_path / "ex")]
    out = vscode.wslify_args(args)
    assert out[out.index("--user-data-dir") + 1] == "/mnt/d/ud"
    assert out[out.index("--extensions-dir") + 1] == "/mnt/d/ex"


def test_write_workspace_debug_config(tmp_path):
    ws = tmp_path / "ws"
    (ws / "artifacts").mkdir(parents=True)
    vscode.write_workspace_debug_config(ws, "/mnt/d/server/.venv/bin/python")
    settings = json.loads((ws / ".vscode" / "settings.json").read_text(encoding="utf-8"))
    launch = json.loads((ws / ".vscode" / "launch.json").read_text(encoding="utf-8"))
    assert settings["python.defaultInterpreterPath"] == "/mnt/d/server/.venv/bin/python"
    assert settings["python.venvPath"] == "/mnt/d/server"
    assert settings["python.testing.pytestPath"] == "/mnt/d/server/.venv/bin/pytest"
    assert settings["python.createEnvironment.trigger"] == "off"
    assert settings["python.testing.cwd"] == "${workspaceFolder}/artifacts"
    names = [c["name"] for c in launch["configurations"]]
    assert "pytest (artifacts)" in names
    pytest_cfg = next(c for c in launch["configurations"] if c["name"] == "pytest (artifacts)")
    assert pytest_cfg["module"] == "pytest"
    assert pytest_cfg["python"] == "/mnt/d/server/.venv/bin/python"
    assert pytest_cfg["cwd"] == "${workspaceFolder}/artifacts"
    assert pytest_cfg["args"] == ["-sv", "."]
    debug_cfg = next(c for c in launch["configurations"] if c["name"] == "Debug Test")
    assert debug_cfg["purpose"] == ["debug-test"]
    assert "module" not in debug_cfg
    assert "program" not in debug_cfg
    assert "args" not in debug_cfg


def test_python_tool_paths_from_venv_python():
    assert vscode.python_tool_paths("/home/u/.venvs/x/bin/python3") == {
        "python.venvPath": "/home/u/.venvs",
        "python.testing.pytestPath": "/home/u/.venvs/x/bin/pytest",
    }


def test_merge_user_python_interpreter(tmp_path):
    user = tmp_path / "code-server" / "user"
    (user / "User").mkdir(parents=True)
    (user / "User" / "settings.json").write_text(
        json.dumps({"telemetry.telemetryLevel": "off"}), encoding="utf-8"
    )
    vscode.merge_user_python_interpreter(user, "/home/u/.venvs/x/bin/python3")
    data = json.loads((user / "User" / "settings.json").read_text(encoding="utf-8"))
    assert data["telemetry.telemetryLevel"] == "off"
    assert data["python.defaultInterpreterPath"] == "/home/u/.venvs/x/bin/python3"
    vscode.merge_user_python_interpreter(user, "/home/u/.venvs/x/bin/python3")
    data2 = json.loads((user / "User" / "settings.json").read_text(encoding="utf-8"))
    assert data2 == data


def test_debug_interpreter_uses_running_python_native(monkeypatch, tmp_path):
    exe = tmp_path / "python.exe"
    exe.write_text("")
    monkeypatch.setattr(vscode.sys, "executable", str(exe))
    assert vscode.debug_interpreter(via_wsl=False) == str(exe.resolve())


def test_debug_interpreter_uses_wsl_path(monkeypatch, tmp_path):
    exe = tmp_path / "python.exe"
    exe.write_text("")
    monkeypatch.setattr(vscode.sys, "executable", str(exe))
    monkeypatch.setattr(vscode, "win_to_wsl_path", lambda p: "/mnt/d/py")
    monkeypatch.setattr(vscode, "detect_wsl_pytest_python", lambda: None)
    assert vscode.debug_interpreter(via_wsl=True) == "/mnt/d/py"


def test_debug_interpreter_prefers_wsl_pytest_venv(monkeypatch, tmp_path):
    exe = tmp_path / "python.exe"
    exe.write_text("")
    monkeypatch.setattr(vscode.sys, "executable", str(exe))
    monkeypatch.setattr(vscode, "detect_wsl_pytest_python", lambda: "/home/u/.venvs/api-test-artifacts/bin/python3")
    assert vscode.debug_interpreter(via_wsl=True) == "/home/u/.venvs/api-test-artifacts/bin/python3"


def test_python_extension_installed_detects_folder(tmp_path):
    ext = tmp_path / "extensions" / "ms-python.python-2024.1.0"
    ext.mkdir(parents=True)
    assert vscode.python_extension_installed(tmp_path / "extensions") is True
    assert vscode.python_extension_installed(tmp_path / "missing") is False


def test_ensure_python_extensions_skips_when_present(tmp_path, monkeypatch):
    py = tmp_path / "ms-python.python-1.0.0"
    syn = py / "syntaxes"
    syn.mkdir(parents=True)
    (syn / "python.tmLanguage.json").write_text('{"scopeName":"source.python"}', encoding="utf-8")
    (py / "package.json").write_text(
        json.dumps(
            {
                "contributes": {
                    "grammars": [
                        {
                            "language": "python",
                            "scopeName": "source.python",
                            "path": "./syntaxes/python.tmLanguage.json",
                        }
                    ],
                    "languages": [{"id": "python", "extensions": [".py"]}],
                }
            }
        ),
        encoding="utf-8",
    )
    called = []
    monkeypatch.setattr(vscode, "_install_open_vsx_extension", lambda *_a, **_k: called.append(1))
    monkeypatch.setattr(vscode, "_open_vsx_download_url", lambda *_a, **_k: called.append(2))
    vscode.ensure_python_extensions(tmp_path)
    assert called == []


def test_ensure_strips_injected_python_grammar_and_drops_magicpython(tmp_path, monkeypatch):
    """内置 vscode.python 已经提供 python 语言 + MagicPython 语法；早前手动往
    ms-python.python 里塞的同名语言/语法贡献，以及手搓的 platform.python-syntax
    UI 扩展，都要在下次 ensure 时被清掉，避免跟内置的重复注册打架。"""
    py = tmp_path / "ms-python.python-2026.4.0-universal"
    (py / "syntaxes").mkdir(parents=True)
    (py / "syntaxes" / "python.tmLanguage.json").write_text('{"scopeName":"source.python"}', encoding="utf-8")
    (py / "package.json").write_text(
        json.dumps(
            {
                "contributes": {
                    "grammars": [
                        {
                            "language": "pip-requirements",
                            "scopeName": "source.pip-requirements",
                            "path": "./syntaxes/pip.json",
                        },
                        {
                            "language": "python",
                            "scopeName": "source.python",
                            "path": "./syntaxes/python.tmLanguage.json",
                        },
                    ],
                    "languages": [
                        {"id": "python", "extensions": [".py", ".pyi", ".pyw"]},
                        {"id": "jinja"},
                    ],
                }
            }
        ),
        encoding="utf-8",
    )
    magic = tmp_path / "magicstack.MagicPython-1.1.1" / "grammars"
    magic.mkdir(parents=True)
    (magic / "MagicPython.tmLanguage").write_text("<plist/>", encoding="utf-8")
    (tmp_path / ".obsolete").write_text('{"magicstack.magicpython-1.1.1":true}', encoding="utf-8")
    ui = tmp_path / "platform.python-syntax-1.0.0"
    (ui / "syntaxes").mkdir(parents=True)
    (ui / "syntaxes" / "python.tmLanguage.json").write_text('{"scopeName":"source.python"}', encoding="utf-8")
    (tmp_path / "extensions.json").write_text(
        json.dumps([{"identifier": {"id": "platform.python-syntax"}, "version": "1.0.0"}]),
        encoding="utf-8",
    )
    monkeypatch.setattr(vscode, "_install_open_vsx_extension", lambda *_a, **_k: None)

    vscode.ensure_python_extensions(tmp_path)

    pkg = json.loads((py / "package.json").read_text(encoding="utf-8"))
    assert not any(g.get("scopeName") == "source.python" for g in pkg["contributes"]["grammars"])
    assert not any(lang.get("id") == "python" for lang in pkg["contributes"]["languages"])
    assert any(lang.get("id") == "jinja" for lang in pkg["contributes"]["languages"])
    assert not (py / "syntaxes" / "python.tmLanguage.json").is_file()
    assert not ui.exists()
    assert not (tmp_path / "magicstack.MagicPython-1.1.1").exists()
    assert not (tmp_path / ".obsolete").exists()
    manifest = json.loads((tmp_path / "extensions.json").read_text(encoding="utf-8"))
    assert not any(e["identifier"]["id"] == "platform.python-syntax" for e in manifest)


def test_extract_vsix_into_extensions_dir(tmp_path):
    import zipfile

    vsix = tmp_path / "ext.vsix"
    with zipfile.ZipFile(vsix, "w") as z:
        z.writestr(
            "extension/package.json",
            json.dumps({"name": "python", "publisher": "ms-python", "version": "1.2.3"}),
        )
        z.writestr("extension/readme.md", "hi")
    dest = tmp_path / "extensions"
    vscode.extract_vsix(vsix, dest)
    installed = dest / "ms-python.python-1.2.3"
    assert (installed / "package.json").is_file()
    assert (installed / "readme.md").read_text(encoding="utf-8") == "hi"


async def test_ensure_writes_workspace_debug_config(mgr, settings, monkeypatch):
    from app.services import workspace as ws_mod

    monkeypatch.setattr(vscode.sys, "executable", str(Path(vscode.sys.executable)))
    monkeypatch.setattr(vscode, "ensure_python_extensions", lambda *_a, **_k: None)
    sid = "s-vs-debug"
    ws = ws_mod.workspace_root(sid)
    ws.mkdir(parents=True, exist_ok=True)
    await mgr.ensure(sid, wait_port=False)
    try:
        assert (ws / ".vscode" / "launch.json").is_file()
        assert (ws / ".vscode" / "settings.json").is_file()
    finally:
        await mgr.shutdown(sid)


async def test_proxy_http(settings, monkeypatch):
    """Use httpx MockTransport to verify forwarding logic without a real code-server."""
    import httpx

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=f"upstream:{request.url.path}")

    resp = _proxy_client(settings, monkeypatch, "s-any", handler).get(
        "/api/sessions/s-any/vscode/some/path"
    )
    assert resp.status_code == 200
    assert resp.text == "upstream:/some/path"


async def test_proxy_rewrites_workbench_base_path(settings, monkeypatch):
    import httpx

    html = (
        "<html><head><meta id=\"vscode-workbench-web-configuration\" "
        "data-settings=\"{&quot;serverBasePath&quot;:&quot;/&quot;,&quot;webviewEndpoint&quot;:&quot;./stable-b7ef8f9bd70cb5b342fa8ec8a0086bad676d8124/static/x&quot;}\"></head></html>"
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/html"}, content=html)

    resp = _proxy_client(settings, monkeypatch, "s-html", handler).get(
        "/api/sessions/s-html/vscode/"
    )
    assert resp.status_code == 200
    assert "/api/sessions/s-html/vscode" in resp.text
    assert "&quot;serverBasePath&quot;:&quot;/&quot;" not in resp.text
    assert resp.headers.get("x-vscode-base-path") == "/api/sessions/s-html/vscode"

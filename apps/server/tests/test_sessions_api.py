import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(settings, monkeypatch, tmp_path):
    monkeypatch.setattr("app.services.workspace._data_dir", settings.data_dir)
    from app.main import build_app

    with TestClient(build_app(settings)) as client:
        yield client


def _origin(tmp_path):
    import subprocess

    origin = tmp_path / "origin"
    origin.mkdir()
    for args in (
        ["init", "-b", "master"],
        ["config", "user.email", "t@t"],
        ["config", "user.name", "t"],
    ):
        subprocess.run(["git", *args], cwd=origin, check=True, capture_output=True)
    (origin / "a.txt").write_text("a")
    subprocess.run(["git", "add", "."], cwd=origin, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "i"], cwd=origin, check=True, capture_output=True)
    subprocess.run(
        ["git", "checkout", "-b", "feature/x"], cwd=origin, check=True, capture_output=True
    )
    return origin


def test_create_and_list(client, tmp_path):
    origin = _origin(tmp_path)
    resp = client.post(
        "/api/sessions",
        json={
            "user_name": "alice",
            "git_url": str(origin),
            "base_branch": "master",
            "feature_branch": "feature/x",
        },
    )
    assert resp.status_code == 202
    sid = resp.json()["id"]
    assert resp.json()["status"] == "cloning"

    # 轮询直到 ready（clone 很快）
    import time

    for _ in range(150):
        detail = client.get(f"/api/sessions/{sid}").json()
        if detail["status"] == "ready":
            break
        time.sleep(0.2)
    assert detail["status"] == "ready"

    listing = client.get("/api/sessions", params={"user_name": "alice"}).json()
    assert any(s["id"] == sid for s in listing)


def test_create_bad_branch_goes_error(client, tmp_path):
    origin = _origin(tmp_path)
    resp = client.post(
        "/api/sessions",
        json={
            "user_name": "alice",
            "git_url": str(origin),
            "base_branch": "master",
            "feature_branch": "no-such",
        },
    )
    sid = resp.json()["id"]
    import time

    for _ in range(150):
        detail = client.get(f"/api/sessions/{sid}").json()
        if detail["status"] == "error":
            break
        time.sleep(0.2)
    assert detail["status"] == "error"
    assert detail["error"]


def test_detail_triggers_restore(client, tmp_path):
    origin = _origin(tmp_path)
    sid = client.post(
        "/api/sessions",
        json={
            "user_name": "bob",
            "git_url": str(origin),
            "base_branch": "master",
            "feature_branch": "feature/x",
        },
    ).json()["id"]
    import time

    for _ in range(150):
        if client.get(f"/api/sessions/{sid}").json()["status"] == "ready":
            break
        time.sleep(0.2)

    from app.services import workspace

    workspace._rmtree(workspace.workspace_root(sid))
    detail = client.get(f"/api/sessions/{sid}").json()
    assert detail["status"] == "restoring"
    for _ in range(150):
        if client.get(f"/api/sessions/{sid}").json()["status"] == "ready":
            break
        time.sleep(0.2)
    assert (workspace.repo_dir(sid) / "a.txt").exists()


def test_delete_soft_and_purge(client, tmp_path):
    origin = _origin(tmp_path)
    sid = client.post(
        "/api/sessions",
        json={
            "user_name": "bob",
            "git_url": str(origin),
            "base_branch": "master",
            "feature_branch": "feature/x",
        },
    ).json()["id"]
    from app.services import workspace

    resp = client.delete(f"/api/sessions/{sid}")
    assert resp.status_code == 204
    assert workspace.workspace_root(sid).exists()  # 软删保留文件

    resp = client.delete(f"/api/sessions/{sid}?purge=true")
    assert resp.status_code == 204
    assert not workspace.workspace_root(sid).exists()


def test_create_rejects_unknown_model(tmp_path, monkeypatch, settings):
    import yaml
    from app.main import build_app
    from app.services.claude_runtime import reset_runtime

    yml = tmp_path / "platform.yaml"
    yml.write_text(
        yaml.safe_dump(
            {
                "claude_home": str(tmp_path / "home"),
                "models": [{"name": "glm-5.3", "default": True, "base_url": "http://a"}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("app.platform_config.resolve_config_path", lambda: yml)
    monkeypatch.setattr("app.services.workspace._data_dir", settings.data_dir)
    reset_runtime()
    with TestClient(build_app(settings)) as client:
        resp = client.post(
            "/api/sessions",
            json={
                "user_name": "alice",
                "git_url": str(tmp_path),
                "base_branch": "master",
                "feature_branch": "f",
                "model": "nope",
            },
        )
        assert resp.status_code == 400
        ok = client.post(
            "/api/sessions",
            json={
                "user_name": "alice",
                "git_url": str(tmp_path),
                "base_branch": "master",
                "feature_branch": "f",
                "model": "glm-5.3",
                "auth_token": "ui",
            },
        )
        assert ok.status_code == 202
        assert ok.json()["model_name"] == "glm-5.3"
        assert "auth_token" not in ok.json()

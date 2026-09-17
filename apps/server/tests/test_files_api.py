import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(settings, monkeypatch):
    monkeypatch.setattr("app.services.workspace._data_dir", settings.data_dir)
    from app.main import build_app
    from app.db import SessionRow
    from app import db as db_mod

    db_mod.init_engine(settings.database_url, settings.data_dir)
    with db_mod.SessionLocal() as s:
        s.add(
            SessionRow(
                id="s-files",
                user_name="u",
                git_url="x",
                base_branch="m",
                feature_branch="f",
                status="ready",
            )
        )
        s.commit()
    from app.services import workspace

    art = workspace.artifacts_dir("s-files")
    (art / "docs").mkdir(parents=True, exist_ok=True)
    (art / "docs" / "00.md").write_text("# hi", encoding="utf-8")
    workspace.repo_dir("s-files").mkdir(parents=True, exist_ok=True)
    return TestClient(build_app(settings))


def test_tree_lists_one_level(client):
    nodes = client.get("/api/sessions/s-files/files/tree").json()
    names = {n["name"] for n in nodes}
    assert "artifacts" in names and "repo" in names
    sub = client.get(
        "/api/sessions/s-files/files/tree", params={"path": "artifacts/docs"}
    ).json()
    assert sub[0]["name"] == "00.md"
    assert sub[0]["type"] == "file"


def test_read_and_write(client):
    resp = client.get(
        "/api/sessions/s-files/files/content", params={"path": "artifacts/docs/00.md"}
    )
    assert resp.json()["content"] == "# hi"

    resp = client.put(
        "/api/sessions/s-files/files/content",
        json={"path": "artifacts/docs/00.md", "content": "# changed"},
    )
    assert resp.status_code == 200
    from app.services import workspace

    assert (
        workspace.artifacts_dir("s-files") / "docs" / "00.md"
    ).read_text(encoding="utf-8") == "# changed"


def test_path_traversal_forbidden(client):
    resp = client.get(
        "/api/sessions/s-files/files/content", params={"path": "../outside.txt"}
    )
    assert resp.status_code == 403

    resp = client.put(
        "/api/sessions/s-files/files/content",
        json={"path": "artifacts/../../evil.txt", "content": "x"},
    )
    assert resp.status_code == 403

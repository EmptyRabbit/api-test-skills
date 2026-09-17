from fastapi.testclient import TestClient


def test_health(settings):
    from app.main import build_app
    client = TestClient(build_app(settings))
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "database" in body


def test_platform_models_empty_by_default(settings):
    from app.main import build_app

    client = TestClient(build_app(settings))
    resp = client.get("/api/platform")
    assert resp.status_code == 200
    assert resp.json() == {"models": [], "user_name": ""}

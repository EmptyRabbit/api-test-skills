import yaml
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import McpOAuthClientRow, SessionRow
from app.platform_config import load_platform_file
from app.services import mcp_oauth

AS_META = {
    "issuer": "https://as.example",
    "registration_endpoint": "https://as.example/register",
    "device_authorization_endpoint": "https://as.example/device",
    "token_endpoint": "https://as.example/token",
    "userinfo_endpoint": "https://as.example/userinfo",
}

OAUTH_SERVERS = {
    "oauth-mcp": {
        "type": "http",
        "url": "http://mcp.example/mcp",
        "auth": "oauth",
        "headers": {"x-token": "t"},
    }
}


def _stub_device_start(monkeypatch, servers=None):
    monkeypatch.setattr(mcp_oauth, "oauth_http_servers", lambda: servers or dict(OAUTH_SERVERS))
    monkeypatch.setattr(mcp_oauth, "discover_as", lambda _url: dict(AS_META))
    monkeypatch.setattr(mcp_oauth, "ensure_client_id", lambda _meta=None: "client-1")
    monkeypatch.setattr(
        mcp_oauth,
        "request_device_authorization",
        lambda **_k: {
            "user_code": "ABCD-EFGH",
            "device_code": "dev-1",
            "interval": 5,
            "expires_in": 1800,
            "verification_uri": "https://as.example/device",
            "verification_uri_complete": "https://as.example/device?user_code=ABCD-EFGH",
        },
    )


def test_load_yaml_keeps_mcp_auth(tmp_path, monkeypatch):
    yml = tmp_path / "platform.yaml"
    yml.write_text(
        yaml.safe_dump(
            {
                "claude_home": str(tmp_path / "home"),
                "mcp_servers": {
                    "oauth-mcp": {
                        "type": "http",
                        "url": "http://mcp.example/mcp",
                        "auth": "oauth",
                        "headers": {"x-token": "t"},
                    },
                    "plain-mcp": {"type": "http", "url": "http://plain.example/mcp"},
                },
                "oauth": {"identity_claims": ["eid", "empCode", "email"]},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("app.platform_config.resolve_config_path", lambda: yml)
    spec = load_platform_file(Settings(data_dir=tmp_path / "data"))
    assert spec.mcp_servers["oauth-mcp"]["auth"] == "oauth"
    assert "auth" not in spec.mcp_servers["plain-mcp"]
    assert mcp_oauth.oauth_server_names(spec.mcp_servers) == ["oauth-mcp"]
    assert spec.oauth.identity_claims == ["eid", "empCode", "email"]


def test_identity_matches_default_email_local_part():
    info = {"eid": "other.user", "mail": "alice.user@example.com"}
    assert mcp_oauth.identity_matches("alice.user", info)
    assert not mcp_oauth.identity_matches("other.user", info)


def test_identity_matches_custom_claims():
    info = {
        "eid": "alice.user",
        "empCode": "S123",
        "account": "ALICE.USER",
        "mail": "other@example.com",
    }
    claims = ["eid", "empCode", "account"]
    assert mcp_oauth.identity_matches("alice.user", info, claims)
    assert mcp_oauth.identity_matches("S123", info, claims)
    assert mcp_oauth.identity_matches("ALICE.USER", info, claims)
    assert not mcp_oauth.identity_matches("other.user", info, claims)


def test_protected_resource_urls():
    urls = mcp_oauth._protected_resource_urls("http://mcp.example/mcp")
    assert urls[0] == "http://mcp.example/.well-known/oauth-protected-resource/mcp"
    assert urls[1] == "http://mcp.example/.well-known/oauth-protected-resource"


def test_discover_as_from_protected_resource(monkeypatch):
    mcp_oauth._as_cache.clear()

    def fake_get(url: str):
        if "protected-resource" in url:
            return {
                "authorization_servers": ["https://as.example"],
                "resource": "http://mcp.example/mcp",
            }
        if url.endswith("/.well-known/oauth-authorization-server"):
            return dict(AS_META)
        raise AssertionError(url)

    monkeypatch.setattr(mcp_oauth, "_resource_metadata_from_www_authenticate", lambda _u: None)
    monkeypatch.setattr(mcp_oauth, "_http_get_json", fake_get)
    meta = mcp_oauth.discover_as("http://mcp.example/mcp")
    assert meta["token_endpoint"] == "https://as.example/token"
    assert meta["device_authorization_endpoint"] == "https://as.example/device"


def test_sdk_mcp_strips_auth_and_adds_bearer():
    out = mcp_oauth.mcp_servers_for_sdk(OAUTH_SERVERS, {"oauth-mcp": "access-token"})
    assert "auth" not in out["oauth-mcp"]
    assert out["oauth-mcp"]["headers"]["Authorization"] == "Bearer access-token"
    assert out["oauth-mcp"]["headers"]["x-token"] == "t"


def test_chat_blocked_when_oauth_missing(settings, monkeypatch):
    monkeypatch.setattr("app.services.workspace._data_dir", settings.data_dir)
    monkeypatch.setattr(mcp_oauth, "missing_oauth_servers", lambda _user: ["oauth-mcp"])
    from app import db as db_mod
    from app.main import build_app

    client = TestClient(build_app(settings))
    with db_mod.SessionLocal() as s:
        s.add(
            SessionRow(
                id="s-oauth",
                user_name="alice",
                git_url="http://example.invalid/x.git",
                base_branch="master",
                feature_branch="f",
                status="ready",
            )
        )
        s.commit()
    resp = client.post("/api/sessions/s-oauth/chat", json={"text": "hi"})
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["code"] == "mcp_oauth_required"
    assert detail["servers"] == ["oauth-mcp"]


def test_oauth_status_and_device_start(settings, monkeypatch):
    monkeypatch.setattr("app.services.workspace._data_dir", settings.data_dir)
    _stub_device_start(monkeypatch)
    from app.main import build_app

    client = TestClient(build_app(settings))
    st = client.get("/api/mcp-login/status", params={"user_name": "alice"}).json()
    assert st["servers"][0]["name"] == "oauth-mcp"
    assert st["servers"][0]["authorized"] is False

    started = client.post(
        "/api/mcp-login/start",
        json={"user_name": "alice", "server": "oauth-mcp"},
    ).json()
    assert started["user_code"] == "ABCD-EFGH"
    assert started["verification_uri_complete"].endswith("ABCD-EFGH")

    monkeypatch.setattr(mcp_oauth, "poll_device_token", lambda **_k: {"status": "pending"})
    polled = client.get(f"/api/mcp-login/flows/{started['flow_id']}").json()
    assert polled["status"] == "pending"


def test_device_poll_saves_token_when_identity_matches(settings, monkeypatch):
    from app import db as db_mod
    from app.main import build_app

    monkeypatch.setattr("app.services.workspace._data_dir", settings.data_dir)
    _stub_device_start(monkeypatch)
    client = TestClient(build_app(settings))
    started = client.post(
        "/api/mcp-login/start",
        json={"user_name": "alice", "server": "oauth-mcp"},
    ).json()
    monkeypatch.setattr(
        mcp_oauth,
        "poll_device_token",
        lambda **_k: {
            "status": "authorized",
            "access_token": "at",
            "refresh_token": "rt",
            "expires_in": 3600,
        },
    )
    monkeypatch.setattr(
        mcp_oauth,
        "fetch_userinfo",
        lambda _token, _ep="": {"mail": "alice@example.com"},
    )
    done = client.get(f"/api/mcp-login/flows/{started['flow_id']}").json()
    assert done["status"] == "authorized"
    assert done["cas_account"] == "alice@example.com"
    assert done["account"] == "alice@example.com"

    with db_mod.SessionLocal() as s:
        row = (
            s.query(mcp_oauth.McpOAuthTokenRow)
            .filter_by(user_name="alice", server_name="oauth-mcp")
            .one()
        )
        assert row.refresh_token == "rt"
        assert row.cas_account == "alice@example.com"


def test_ensure_client_id_uses_db_when_json_missing(settings, monkeypatch):
    from app import db as db_mod

    monkeypatch.setattr(mcp_oauth, "_data_dir", lambda: settings.data_dir)
    db_mod.init_engine(settings.database_url, settings.data_dir)
    posts = {"n": 0}

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"client_id": "cid-db"}

    class _Client:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return None

        def post(self, _url, json=None):
            posts["n"] += 1
            return _Resp()

    monkeypatch.setattr(mcp_oauth.httpx, "Client", lambda **_k: _Client())
    assert mcp_oauth.ensure_client_id(AS_META) == "cid-db"
    assert not (settings.data_dir / "mcp-oauth-client.json").exists()
    assert mcp_oauth.ensure_client_id(AS_META) == "cid-db"
    assert posts["n"] == 1
    with db_mod.SessionLocal() as s:
        row = s.query(McpOAuthClientRow).filter_by(issuer=AS_META["issuer"]).one()
        assert row.client_id == "cid-db"


def test_ensure_client_id_migrates_legacy_json(settings, monkeypatch):
    from app import db as db_mod

    settings.data_dir.mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "mcp-oauth-client.json").write_text(
        '{"client_id": "cid-legacy"}', encoding="utf-8"
    )
    monkeypatch.setattr(mcp_oauth, "_data_dir", lambda: settings.data_dir)
    db_mod.init_engine(settings.database_url, settings.data_dir)

    def _no_post(*_a, **_k):
        raise AssertionError("should not re-register")

    monkeypatch.setattr(mcp_oauth.httpx, "Client", _no_post)
    assert mcp_oauth.ensure_client_id(AS_META) == "cid-legacy"
    (settings.data_dir / "mcp-oauth-client.json").unlink()
    assert mcp_oauth.ensure_client_id(AS_META) == "cid-legacy"
    with db_mod.SessionLocal() as s:
        row = s.query(McpOAuthClientRow).filter_by(issuer=AS_META["issuer"]).one()
        assert row.client_id == "cid-legacy"


def test_clears_needs_auth_cache(tmp_path):
    cache = tmp_path / "mcp-needs-auth-cache.json"
    cache.write_text('{"oauth-mcp":{"timestamp":1},"plain-mcp":{"timestamp":2}}', encoding="utf-8")
    mcp_oauth.clear_needs_auth_cache(cache, ["oauth-mcp"])
    import json

    assert json.loads(cache.read_text(encoding="utf-8")) == {"plain-mcp": {"timestamp": 2}}

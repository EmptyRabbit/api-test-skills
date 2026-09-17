"""Device-code OAuth for HTTP MCP servers marked auth: oauth.

Authorization server URLs come from RFC 9728 protected-resource metadata
on the MCP URL, then RFC 8414 authorization-server metadata. No vendor
IdP is hardcoded.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse

import httpx

from app.db import McpOAuthClientRow, McpOAuthTokenRow

logger = logging.getLogger(__name__)

DEVICE_GRANT = "urn:ietf:params:oauth:grant-type:device_code"
_WWW_METADATA = re.compile(r'resource_metadata=(?:"([^"]+)"|([^\s,]+))', re.I)

_lock = threading.Lock()
_flows: dict[str, dict[str, Any]] = {}
_as_cache: dict[str, dict[str, Any]] = {}


def _runtime():
    from app.services.claude_runtime import get_runtime

    return get_runtime()


def _is_oauth(cfg: dict) -> bool:
    return str(cfg.get("auth") or "").lower() == "oauth"


def oauth_server_names(servers: dict[str, dict]) -> list[str]:
    return sorted(name for name, cfg in (servers or {}).items() if _is_oauth(cfg))


def oauth_http_servers() -> dict[str, dict]:
    return {n: dict(cfg) for n, cfg in _runtime().mcp_servers.items() if _is_oauth(cfg)}


def identity_claims() -> list[str]:
    return list(_runtime().spec.oauth.identity_claims)


def identity_matches(user_name: str, info: dict, claims: list[str] | None = None) -> bool:
    want = (user_name or "").strip().lower()
    if not want:
        return False
    names: set[str] = set()
    for key in claims if claims is not None else identity_claims():
        val = info.get(key)
        if not val:
            continue
        text = str(val).strip().lower()
        names.add(text)
        if "@" in text:
            names.add(text.split("@", 1)[0])
    return want in names


def account_of(info: dict, claims: list[str] | None = None) -> str:
    for key in claims if claims is not None else identity_claims():
        val = info.get(key)
        if val:
            return str(val).strip()
    return ""


def mcp_servers_for_sdk(
    servers: dict[str, dict], access_tokens: dict[str, str]
) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for name, cfg in (servers or {}).items():
        item = {k: v for k, v in cfg.items() if k != "auth"}
        if name in access_tokens:
            headers = dict(item.get("headers") or {})
            headers["Authorization"] = f"Bearer {access_tokens[name]}"
            item["headers"] = headers
        out[name] = item
    return out


def _load_json(path: Path):
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def clear_needs_auth_cache(cache_path: Path, servers: list[str]) -> None:
    data = _load_json(cache_path)
    if not isinstance(data, dict):
        return
    changed = False
    for name in servers:
        if name in data:
            data.pop(name)
            changed = True
    if changed:
        cache_path.write_text(json.dumps(data), encoding="utf-8")


def _data_dir() -> Path:
    return _runtime().spec.claude_home.parent


def _http_get_json(url: str, extra_headers: dict | None = None) -> dict:
    headers = {"Accept": "application/json", **(extra_headers or {})}
    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
        resp = client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()


def _protected_resource_urls(mcp_url: str) -> list[str]:
    parsed = urlparse(mcp_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    path = (parsed.path or "").rstrip("/")
    urls: list[str] = []
    if path:
        urls.append(f"{origin}/.well-known/oauth-protected-resource{path}")
    urls.append(f"{origin}/.well-known/oauth-protected-resource")
    return urls


def _resource_metadata_from_www_authenticate(mcp_url: str) -> str | None:
    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            resp = client.get(mcp_url, headers={"Accept": "application/json"})
    except httpx.HTTPError:
        return None
    www = resp.headers.get("www-authenticate") or ""
    match = _WWW_METADATA.search(www)
    if not match:
        return None
    return (match.group(1) or match.group(2) or "").strip() or None


def _normalize_as_meta(raw: dict, issuer: str) -> dict:
    device = raw.get("device_authorization_endpoint")
    token = raw.get("token_endpoint")
    register = raw.get("registration_endpoint")
    if not device or not token or not register:
        raise RuntimeError(
            "授权服务器元数据缺少 device_authorization_endpoint / token_endpoint / registration_endpoint"
        )
    return {
        "issuer": str(raw.get("issuer") or issuer).rstrip("/"),
        "device_authorization_endpoint": str(device),
        "token_endpoint": str(token),
        "registration_endpoint": str(register),
        "userinfo_endpoint": str(raw.get("userinfo_endpoint") or ""),
    }


def discover_as(mcp_url: str) -> dict:
    key = mcp_url.rstrip("/")
    with _lock:
        cached = _as_cache.get(key)
    if cached:
        return cached
    urls: list[str] = []
    www = _resource_metadata_from_www_authenticate(mcp_url)
    if www:
        urls.append(www)
    urls.extend(_protected_resource_urls(mcp_url))
    resource_doc: dict | None = None
    last_err: Exception | None = None
    seen: set[str] = set()
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        try:
            resource_doc = _http_get_json(url)
            break
        except Exception as exc:
            last_err = exc
    if not resource_doc:
        raise RuntimeError(f"无法发现 MCP OAuth 资源元数据: {mcp_url}") from last_err
    servers = resource_doc.get("authorization_servers") or []
    if not servers:
        raise RuntimeError("oauth-protected-resource 未声明 authorization_servers")
    issuer = str(servers[0]).rstrip("/")
    as_url = f"{issuer}/.well-known/oauth-authorization-server"
    meta = _normalize_as_meta(_http_get_json(as_url), issuer)
    with _lock:
        _as_cache[key] = meta
    return meta


def _client_id_from_db(issuer: str) -> str | None:
    from app import db

    if db.SessionLocal is None:
        return None
    with db.SessionLocal() as s:
        row = s.query(McpOAuthClientRow).filter_by(issuer=issuer).one_or_none()
        return row.client_id if row and row.client_id else None


def _client_id_from_json(issuer: str) -> str | None:
    path = _data_dir() / "mcp-oauth-client.json"
    loaded = _load_json(path)
    if not isinstance(loaded, dict):
        return None
    nested = loaded.get(issuer)
    if isinstance(nested, dict) and nested.get("client_id"):
        return str(nested["client_id"])
    legacy = loaded.get("client_id")
    if isinstance(legacy, str) and legacy:
        return legacy
    return None


def _save_client_id(issuer: str, client_id: str) -> None:
    from app import db

    if db.SessionLocal is None:
        raise RuntimeError("数据库未初始化，无法保存 OAuth client_id")
    with db.SessionLocal() as s:
        row = s.query(McpOAuthClientRow).filter_by(issuer=issuer).one_or_none()
        if row is None:
            s.add(McpOAuthClientRow(issuer=issuer, client_id=client_id))
        else:
            row.client_id = client_id
        s.commit()


def ensure_client_id(as_meta: dict) -> str:
    if not as_meta:
        raise RuntimeError("缺少授权服务器元数据")
    issuer = str(as_meta.get("issuer") or "")
    register = str(as_meta.get("registration_endpoint") or "")
    if not issuer or not register:
        raise RuntimeError("授权服务器未提供 registration_endpoint")
    with _lock:
        found = _client_id_from_db(issuer)
        if found:
            return found
        found = _client_id_from_json(issuer)
        if found:
            _save_client_id(issuer, found)
            return found
        payload = {
            "client_name": "api-test-skills-platform",
            "redirect_uris": ["http://127.0.0.1/device/callback"],
            "grant_types": [DEVICE_GRANT, "refresh_token"],
            "token_endpoint_auth_method": "none",
            "application_type": "native",
        }
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(register, json=payload)
            resp.raise_for_status()
            body = resp.json()
        cid = body.get("client_id")
        if not cid:
            raise RuntimeError(f"OAuth 动态注册客户端失败: {body}")
        cid = str(cid)
        _save_client_id(issuer, cid)
        return cid


def _form_post(url: str, data: dict[str, str]) -> httpx.Response:
    with httpx.Client(timeout=20.0) as client:
        return client.post(
            url,
            content=urlencode(data),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )


def request_device_authorization(
    *, client_id: str, resource: str, device_endpoint: str
) -> dict:
    resp = _form_post(
        device_endpoint,
        {
            "client_id": client_id,
            "scope": "openid profile email",
            "resource": resource,
        },
    )
    resp.raise_for_status()
    return resp.json()


def poll_device_token(
    *, client_id: str, device_code: str, resource: str, token_endpoint: str
) -> dict:
    resp = _form_post(
        token_endpoint,
        {
            "grant_type": DEVICE_GRANT,
            "device_code": device_code,
            "client_id": client_id,
            "resource": resource,
        },
    )
    try:
        data = resp.json()
    except (json.JSONDecodeError, ValueError):
        data = {"error": resp.text}
    if resp.status_code == 200 and data.get("access_token"):
        return {
            "status": "authorized",
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token") or "",
            "expires_in": int(data.get("expires_in") or 3600),
        }
    err = str(data.get("error") or "")
    if err in ("authorization_pending", "slow_down") or resp.status_code in (400, 428):
        return {"status": "pending", "error": err or "authorization_pending"}
    return {
        "status": "error",
        "error": err or f"http_{resp.status_code}",
        "error_description": data.get("error_description") or "",
    }


def fetch_userinfo(access_token: str, userinfo_endpoint: str) -> dict:
    return _http_get_json(
        userinfo_endpoint,
        extra_headers={"Authorization": f"Bearer {access_token}"},
    )


def _expires_at(expires_in) -> datetime:
    return datetime.now(timezone.utc) + timedelta(
        seconds=max(int(expires_in or 3600) - 30, 60)
    )


def _account_fields(account: str) -> dict:
    return {"account": account, "cas_account": account}


def _token_rows(s, user_name: str, servers: dict) -> dict[str, McpOAuthTokenRow]:
    found = (
        s.query(McpOAuthTokenRow)
        .filter(
            McpOAuthTokenRow.user_name == user_name,
            McpOAuthTokenRow.server_name.in_(list(servers)),
        )
        .all()
    )
    return {r.server_name: r for r in found}


def _refresh_access(row: McpOAuthTokenRow, client_id: str, token_endpoint: str) -> str | None:
    if not row.refresh_token:
        return None
    resp = _form_post(
        token_endpoint,
        {
            "grant_type": "refresh_token",
            "refresh_token": row.refresh_token,
            "client_id": client_id,
            "resource": row.resource,
        },
    )
    if resp.status_code != 200:
        logger.warning("mcp oauth refresh failed server=%s status=%s", row.server_name, resp.status_code)
        return None
    data = resp.json()
    token = data.get("access_token")
    if not token:
        return None
    row.access_token = token
    if data.get("refresh_token"):
        row.refresh_token = data["refresh_token"]
    row.expires_at = _expires_at(data.get("expires_in"))
    return token


def _token_fresh(row: McpOAuthTokenRow) -> bool:
    if not row.access_token or row.expires_at is None:
        return False
    exp = row.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return exp > datetime.now(timezone.utc) + timedelta(seconds=30)


def missing_oauth_servers(user_name: str) -> list[str]:
    return [s["name"] for s in status_for_user(user_name) if not s["authorized"]]


def status_for_user(user_name: str) -> list[dict]:
    from app import db

    servers = oauth_http_servers()
    rows: dict[str, McpOAuthTokenRow] = {}
    if db.SessionLocal is not None and servers:
        with db.SessionLocal() as s:
            rows = _token_rows(s, user_name, servers)
    out = []
    for name in servers:
        row = rows.get(name)
        out.append(
            {
                "name": name,
                "authorized": bool(row and row.refresh_token),
                **_account_fields((row.cas_account if row else "") or ""),
            }
        )
    return out


def start_device_flow(user_name: str, server: str) -> dict:
    servers = oauth_http_servers()
    cfg = servers.get(server)
    if cfg is None:
        raise KeyError(server)
    resource = str(cfg.get("url") or "")
    meta = discover_as(resource)
    client_id = ensure_client_id(meta)
    started = request_device_authorization(
        client_id=client_id,
        resource=resource,
        device_endpoint=meta["device_authorization_endpoint"],
    )
    flow_id = uuid.uuid4().hex
    with _lock:
        _flows[flow_id] = {
            "user_name": user_name,
            "server": server,
            "resource": resource,
            "client_id": client_id,
            "device_code": started["device_code"],
            "token_endpoint": meta["token_endpoint"],
            "userinfo_endpoint": meta.get("userinfo_endpoint") or "",
            "interval": int(started.get("interval") or 5),
            "expires_at": datetime.now(timezone.utc)
            + timedelta(seconds=int(started.get("expires_in") or 1800)),
        }
    return {
        "flow_id": flow_id,
        "server": server,
        "user_code": started.get("user_code"),
        "verification_uri": started.get("verification_uri"),
        "verification_uri_complete": started.get("verification_uri_complete"),
        "interval": int(started.get("interval") or 5),
        "expires_in": int(started.get("expires_in") or 1800),
    }


def _save_token(flow: dict, token: dict, info: dict) -> str:
    from app import db

    account = account_of(info)
    expires = _expires_at(token.get("expires_in"))

    def write(s):
        row = (
            s.query(McpOAuthTokenRow)
            .filter_by(user_name=flow["user_name"], server_name=flow["server"])
            .one_or_none()
        )
        if row is None:
            row = McpOAuthTokenRow(
                user_name=flow["user_name"],
                server_name=flow["server"],
            )
            s.add(row)
        row.access_token = token["access_token"]
        row.refresh_token = token.get("refresh_token") or ""
        row.cas_account = account
        row.resource = flow["resource"]
        row.expires_at = expires
        s.commit()

    with db.SessionLocal() as s:
        write(s)
    return account


def poll_flow(flow_id: str) -> dict:
    with _lock:
        flow = _flows.get(flow_id)
    if flow is None:
        return {"status": "error", "error": "unknown_flow"}
    if datetime.now(timezone.utc) > flow["expires_at"]:
        with _lock:
            _flows.pop(flow_id, None)
        return {"status": "error", "error": "expired_token"}
    token = poll_device_token(
        client_id=flow["client_id"],
        device_code=flow["device_code"],
        resource=flow["resource"],
        token_endpoint=flow["token_endpoint"],
    )
    if token.get("status") != "authorized":
        return token
    info: dict = {}
    userinfo = flow.get("userinfo_endpoint") or ""
    if userinfo:
        info = fetch_userinfo(token["access_token"], userinfo)
        if not identity_matches(flow["user_name"], info):
            with _lock:
                _flows.pop(flow_id, None)
            account = account_of(info)
            return {
                "status": "mismatch",
                **_account_fields(account),
                "user_name": flow["user_name"],
            }
    account = _save_token(flow, token, info)
    with _lock:
        _flows.pop(flow_id, None)
    return {
        "status": "authorized",
        **_account_fields(account),
        "server": flow["server"],
    }


def access_tokens_for_user(user_name: str) -> dict[str, str]:
    from app import db

    servers = oauth_http_servers()
    if not servers or db.SessionLocal is None:
        return {}
    tokens: dict[str, str] = {}
    with db.SessionLocal() as s:
        rows = list(_token_rows(s, user_name, servers).values())
        meta_by_resource: dict[str, dict] = {}
        for row in rows:
            if _token_fresh(row):
                tokens[row.server_name] = row.access_token
                continue
            try:
                meta = meta_by_resource.get(row.resource)
                if meta is None:
                    meta = discover_as(row.resource)
                    meta_by_resource[row.resource] = meta
                refreshed = _refresh_access(row, ensure_client_id(meta), meta["token_endpoint"])
            except Exception:
                logger.exception("mcp oauth refresh discover failed server=%s", row.server_name)
                refreshed = None
            if refreshed:
                tokens[row.server_name] = refreshed
        s.commit()
    return tokens


def mcp_servers_for_user(user_name: str) -> dict[str, dict]:
    runtime = _runtime()
    tokens = access_tokens_for_user(user_name)
    out = mcp_servers_for_sdk(runtime.mcp_servers, tokens)
    if tokens:
        clear_needs_auth_cache(
            runtime.spec.claude_home / "mcp-needs-auth-cache.json",
            list(tokens),
        )
    return out

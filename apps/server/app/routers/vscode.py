import asyncio
import re
import time
from urllib.parse import unquote

import httpx
from fastapi import APIRouter, HTTPException, Request, WebSocket
from fastapi.responses import Response, StreamingResponse
from websockets.asyncio.client import connect

from app import db
from app.routers.sessions import _get
from app.services import vscode

router = APIRouter(prefix="/api/sessions", tags=["vscode"])

HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
}
STRIP_RESPONSE_HEADERS = HOP_HEADERS | {"content-encoding"}

_STRIP_WORKBENCH_URLS = (
    "https://open-vsx.org/vscode/gallery",
    "https://open-vsx.org/vscode/item",
    "https://open-vsx.org/vscode/asset/{publisher}/{name}/{version}/Microsoft.VisualStudio.Code.WebResources/{path}",
    "https://v1.telemetry.coder.com/track",
)


_COMMIT_RE = re.compile(r"stable-([0-9a-f]{40})")
_CDN_EXT_MARKERS = (
    "vscode-cdn.net/extensions/",
    "https://vscode-cdn.net/extensions/",
    "http://vscode-cdn.net/extensions/",
)
# workbench 把内置扩展资源错解析到当前页 query / oss-dev 时，用这里记下的 commit 转回本地 static。
_workbench_commits: dict[str, str] = {}


def vscode_public_prefix(sid: str) -> str:
    return f"/api/sessions/{sid}/vscode"


def remember_workbench_commit(prefix: str, html: str) -> str | None:
    found = _COMMIT_RE.search(html)
    if found:
        _workbench_commits[prefix.rstrip("/")] = found.group(1)
        return found.group(1)
    return _workbench_commits.get(prefix.rstrip("/"))


def remap_vscode_asset_request(sid: str, path: str, query: str) -> tuple[str, str]:
    """纠正 workbench 在子路径代理下拼错的内置扩展资源 URL。

    常见两种：
    1. pathname + serverBasePath 叠成两段 /api/sessions/.../vscode/.../vscode-remote-resource
    2. 退化成当前页 query：?vscode-cdn.net/extensions/...
    """
    prefix = vscode_public_prefix(sid).lstrip("/")
    while path.startswith(prefix + "/"):
        path = path[len(prefix) + 1 :]
    found = _COMMIT_RE.search(path)
    if found:
        _workbench_commits[vscode_public_prefix(sid)] = found.group(1)
    if path == "vscode-remote-resource" or path.endswith("/vscode-remote-resource"):
        return "vscode-remote-resource", query
    commit = _workbench_commits.get(vscode_public_prefix(sid))
    if not commit:
        return path, query
    q = unquote((query or "").split("&", 1)[0]).rstrip("=")
    rel = None
    for marker in _CDN_EXT_MARKERS:
        if q.startswith(marker):
            rel = q.split("/extensions/", 1)[-1]
            break
    if rel is None and "/extensions/" in path and ("oss-dev/" in path or "vscode-cdn.net" in path):
        rel = path.split("/extensions/", 1)[-1]
    if not rel or ".." in rel or rel.startswith("/"):
        return path, query
    return f"stable-{commit}/static/extensions/{rel}", ""


def rewrite_workbench_html(html: str, prefix: str) -> str:
    """改写子路径，补上 quality/commit，并去掉扩展市场 / 遥测外网地址。"""
    prefix = prefix.rstrip("/")
    commit = remember_workbench_commit(prefix, html)
    for q in ("&quot;", '"'):
        html = html.replace(f"{q}serverBasePath{q}:{q}/{q}", f"{q}serverBasePath{q}:{q}{prefix}{q}")
        html = html.replace(f"{q}enableTelemetry{q}:true", f"{q}enableTelemetry{q}:false")
        if commit and f"{q}commit{q}:" not in html:
            html = html.replace(
                f"{q}productConfiguration{q}:{{",
                f"{q}productConfiguration{q}:{{{q}quality{q}:{q}stable{q},{q}commit{q}:{q}{commit}{q},",
                1,
            )
    for url in _STRIP_WORKBENCH_URLS:
        html = html.replace(url, "")
    return html


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=httpx.Timeout(connect=5.0, read=60.0, write=30.0, pool=5.0)
    )


def _drop_headers(headers, drop: set[str]) -> dict:
    return {k: v for k, v in headers.items() if k.lower() not in drop}


def _loopback_url(scheme: str, port: int, path: str, query: str) -> str:
    url = f"{scheme}://127.0.0.1:{port}/{path}"
    return f"{url}?{query}" if query else url


async def _ensure_port(sid: str) -> int:
    try:
        return await vscode.manager.ensure(sid)
    except vscode.CodeServerError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


def _touch(sid: str) -> None:
    inst = vscode.manager.instances.get(sid)
    if inst:
        inst.last_active = time.time()


@router.post("/{sid}/vscode/ensure")
async def ensure_vscode(sid: str):
    await db.run_db(lambda s: _get(s, sid))
    port = await _ensure_port(sid)
    return {"port": port, "ready": True}


@router.api_route(
    "/{sid}/vscode",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
)
@router.api_route(
    "/{sid}/vscode/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
)
async def proxy_http(sid: str, request: Request, path: str = ""):
    await db.run_db(lambda s: _get(s, sid))
    port = await _ensure_port(sid)
    path, query = remap_vscode_asset_request(sid, path, request.url.query)
    headers = _drop_headers(request.headers, HOP_HEADERS)
    body = await request.body()
    client = _client()
    req = client.build_request(
        request.method,
        _loopback_url("http", port, path, query),
        headers=headers,
        content=body,
    )
    resp = await client.send(req, stream=True)
    _touch(sid)

    passthrough = _drop_headers(resp.headers, STRIP_RESPONSE_HEADERS)
    if path.endswith(".wasm"):
        passthrough["content-type"] = "application/wasm"
    ctype = (passthrough.get("content-type") or "").lower()
    if "text/html" in ctype:
        raw = await resp.aread()
        await resp.aclose()
        await client.aclose()
        prefix = vscode_public_prefix(sid)
        html = rewrite_workbench_html(raw.decode("utf-8", "replace"), prefix)
        passthrough.pop("content-length", None)
        passthrough["x-vscode-base-path"] = prefix
        passthrough["cache-control"] = "no-store"
        return Response(content=html, status_code=resp.status_code, headers=passthrough)

    async def relay():
        try:
            async for chunk in resp.aiter_bytes():
                yield chunk
        finally:
            await resp.aclose()
            await client.aclose()

    return StreamingResponse(relay(), status_code=resp.status_code, headers=passthrough)


@router.websocket("/{sid}/vscode")
@router.websocket("/{sid}/vscode/{path:path}")
async def proxy_ws(ws: WebSocket, sid: str, path: str = ""):
    try:
        await db.run_db(lambda s: _get(s, sid))
    except Exception:
        await ws.close(code=4404)
        return
    subprotocol = ws.headers.get("sec-websocket-protocol")
    chosen = subprotocol.split(",")[0].strip() if subprotocol else None
    await ws.accept(subprotocol=chosen)
    try:
        port = await _ensure_port(sid)
    except HTTPException:
        await ws.close(code=1011)
        return
    target = _loopback_url("ws", port, path, ws.url.query or "")
    connect_kw: dict = {
        "max_size": None,
        "origin": f"http://127.0.0.1:{port}",
    }
    if chosen:
        connect_kw["subprotocols"] = [chosen]
    try:
        upstream = await connect(target, **connect_kw)
    except Exception:
        await ws.close(code=1011)
        return

    _touch(sid)

    async def pump_client_to_upstream():
        try:
            while True:
                msg = await ws.receive()
                if msg["type"] == "websocket.disconnect":
                    break
                if msg.get("bytes") is not None:
                    await upstream.send(msg["bytes"])
                elif msg.get("text") is not None:
                    await upstream.send(msg["text"])
        except Exception:
            pass

    async def pump_upstream_to_client():
        try:
            async for msg in upstream:
                if isinstance(msg, str):
                    await ws.send_text(msg)
                else:
                    await ws.send_bytes(msg)
        except Exception:
            pass

    await asyncio.gather(
        pump_client_to_upstream(),
        pump_upstream_to_client(),
        return_exceptions=True,
    )
    await upstream.close()
    try:
        await ws.close()
    except Exception:
        pass

import asyncio

import pytest


@pytest.mark.asyncio
async def test_bus_pubsub():
    from app.services.bus import SessionBus

    b = SessionBus()
    q = b.subscribe("s1")
    await b.publish("s1", {"type": "agent_message", "role": "assistant", "blocks": []})
    b.unsubscribe("s1", q)
    await b.publish("s1", {"type": "agent_done"})  # 无订阅者不报错
    event = await asyncio.wait_for(q.get(), timeout=5)
    assert event == {"type": "agent_message", "role": "assistant", "blocks": []}


@pytest.mark.asyncio
async def test_sse_stream(settings):
    """
    Drive the ASGI app directly in the test's event loop.

    We cannot use TestClient (or httpx ASGITransport) here: both run the app
    to completion and buffer the whole body before returning, so an infinite
    SSE stream hangs them.  Instead we call the app as a task in the same
    loop, which lets us assert on headers, then publish to the bus and see
    the event framed as SSE, then cancel the request.

    The endpoint subscribes before StreamingResponse sends ``http.response.start``,
    so once ``started`` is set the subscription is guaranteed to exist.
    """
    from app.main import build_app
    from app.services.bus import bus

    app = build_app(settings)
    sid = "s-sse"

    started = asyncio.Event()
    got_body = asyncio.Event()
    info: dict = {}
    body: list[bytes] = []

    async def receive():
        # never deliver http.disconnect; the request lives until we cancel
        await asyncio.Event().wait()

    async def send(message):
        if message["type"] == "http.response.start":
            info["status"] = message["status"]
            info["headers"] = dict(message.get("headers") or [])
            started.set()
        elif message["type"] == "http.response.body" and message.get("body"):
            body.append(message["body"])
            got_body.set()

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": f"/api/sessions/{sid}/events",
        "raw_path": f"/api/sessions/{sid}/events".encode(),
        "query_string": b"",
        "headers": [(b"host", b"testserver")],
        "client": ("127.0.0.1", 123),
        "server": ("testserver", 80),
    }

    task = asyncio.create_task(app(scope, receive, send))
    await asyncio.wait_for(started.wait(), timeout=5)
    assert info["status"] == 200
    assert info["headers"][b"content-type"].startswith(b"text/event-stream")

    await bus.publish(sid, {"type": "agent_done", "duration_ms": 5})
    await asyncio.wait_for(got_body.wait(), timeout=5)
    text = b"".join(body).decode()
    assert "event: agent_done\n" in text
    assert '"type": "agent_done"' in text
    assert '"duration_ms": 5' in text

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

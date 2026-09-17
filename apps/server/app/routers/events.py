import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.services.bus import bus

router = APIRouter(prefix="/api/sessions", tags=["events"])

_POLL_TIMEOUT = 30  # seconds; keeps the generator interruptible


@router.get("/{sid}/events")
async def session_events(sid: str):
    q = bus.subscribe(sid)

    async def gen():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=_POLL_TIMEOUT)
                except asyncio.TimeoutError:
                    # send a keep-alive comment and loop again
                    yield ": keep-alive\n\n"
                    continue
                yield (
                    f"event: {event['type']}\n"
                    f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                )
        finally:
            bus.unsubscribe(sid, q)

    return StreamingResponse(gen(), media_type="text/event-stream")

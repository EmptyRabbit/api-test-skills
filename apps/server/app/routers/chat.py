import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import db
from app.db import MessageRow
from app.routers.sessions import _get, _set_status
from app.services import agent, mcp_oauth
from app.services.bus import bus

router = APIRouter(prefix="/api/sessions", tags=["chat"])


class ChatIn(BaseModel):
    text: str


@router.get("/{sid}/messages")
async def list_messages(sid: str):
    await db.run_db(lambda s: _get(s, sid))

    def q(s):
        rows = (
            s.query(MessageRow)
            .filter(MessageRow.session_id == sid)
            .order_by(MessageRow.id.asc())
            .all()
        )
        return [
            {"role": r.role, "blocks": r.content, "id": r.id} for r in rows
        ]

    return await db.run_db(q)


@router.post("/{sid}/chat", status_code=202)
async def chat(sid: str, body: ChatIn):
    row = await db.run_db(lambda s: _get(s, sid))
    if sid in agent._running:
        raise HTTPException(status_code=409, detail="agent is running")
    if row.status != "ready":
        raise HTTPException(status_code=409, detail=f"session status is {row.status}")
    missing = await asyncio.to_thread(mcp_oauth.missing_oauth_servers, row.user_name)
    if missing:
        raise HTTPException(
            status_code=409,
            detail={"code": "mcp_oauth_required", "servers": missing},
        )

    await db.run_db(_set_status(sid, "running"))
    await bus.publish(
        sid,
        {
            "type": "agent_message",
            "role": "user",
            "blocks": [{"kind": "text", "text": body.text}],
        },
    )
    await agent.save_message(sid, "user", [{"kind": "text", "text": body.text}])
    asyncio.get_running_loop().create_task(
        agent.run_agent_turn(sid, body.text)
    )
    return {"ok": True}


@router.post("/{sid}/stop")
async def stop(sid: str):
    await db.run_db(lambda s: _get(s, sid))
    stopped = await agent.stop_agent(sid)
    return {"stopped": stopped}

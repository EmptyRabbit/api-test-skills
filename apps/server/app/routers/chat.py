from fastapi import APIRouter
from pydantic import BaseModel

from app import db
from app.db import MessageRow
from app.services import agent, lifecycle

router = APIRouter(prefix="/api/sessions", tags=["chat"])


class ChatIn(BaseModel):
    text: str


@router.get("/{sid}/messages")
async def list_messages(sid: str):
    await lifecycle.get_session(sid)

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
    await lifecycle.begin_turn(sid, body.text)
    return {"ok": True}


@router.post("/{sid}/stop")
async def stop(sid: str):
    await lifecycle.get_session(sid)
    stopped = await agent.stop_agent(sid)
    return {"stopped": stopped}

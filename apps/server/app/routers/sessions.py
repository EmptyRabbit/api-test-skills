from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app import db
from app.db import SessionRow, new_session_id
from app.services import lifecycle

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class SessionCreate(BaseModel):
    user_name: str
    git_url: str
    base_branch: str
    feature_branch: str
    model: str | None = None
    auth_token: str | None = None


class SessionOut(BaseModel):
    id: str
    user_name: str
    git_url: str
    base_branch: str
    feature_branch: str
    title: str
    status: str
    error: str
    model_name: str = ""
    created_at: str


def _to_out(s: SessionRow) -> SessionOut:
    return SessionOut(
        id=s.id,
        user_name=s.user_name,
        git_url=s.git_url,
        base_branch=s.base_branch,
        feature_branch=s.feature_branch,
        title=s.title,
        status=s.status,
        error=s.error,
        model_name=s.model_name or "",
        created_at=s.created_at.isoformat(),
    )


@router.post("", status_code=202)
async def create_session(body: SessionCreate):
    from app.platform_config import PlatformConfigError
    from app.services.claude_runtime import get_runtime, resolve_model

    try:
        chosen = resolve_model(get_runtime().spec, body.model, body.auth_token)
    except PlatformConfigError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    sid = new_session_id()

    def _insert(s):
        s.add(
            SessionRow(
                id=sid,
                user_name=body.user_name,
                git_url=body.git_url,
                base_branch=body.base_branch,
                feature_branch=body.feature_branch,
                title=body.git_url.rsplit("/", 1)[-1],
                model_name=chosen.name or "",
                auth_token=(body.auth_token or "").strip(),
            )
        )
        s.commit()

    await db.run_db(_insert)
    lifecycle.kick_clone(sid)
    row = await db.run_db(lambda s: s.get(SessionRow, sid))
    return _to_out(row)


@router.get("")
async def list_sessions(user_name: str = ""):
    def q(s):
        rows = s.query(SessionRow).filter(SessionRow.deleted == False)  # noqa: E712
        if user_name:
            rows = rows.filter(SessionRow.user_name == user_name)
        rows = rows.order_by(SessionRow.updated_at.desc()).all()
        return [_to_out(r) for r in rows]

    return await db.run_db(q)


@router.get("/{sid}")
async def get_session(sid: str):
    row = await lifecycle.get_session(sid)
    row = await lifecycle.rehydrate(row)
    return _to_out(row)


@router.post("/{sid}/snapshots")
async def manual_snapshot(sid: str):
    await lifecycle.get_session(sid)
    from app.services.snapshots import take_snapshot

    n = await take_snapshot(sid, "manual")
    return {"files": n}


@router.delete("/{sid}", status_code=204)
async def delete_session(sid: str, purge: bool = Query(False)):
    await lifecycle.delete_session(sid, purge=purge)

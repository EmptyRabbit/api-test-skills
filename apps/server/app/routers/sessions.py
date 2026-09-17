import asyncio
import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app import db
from app.db import SessionRow, new_session_id
from app.services import workspace

router = APIRouter(prefix="/api/sessions", tags=["sessions"])
logger = logging.getLogger(__name__)


class SessionCreate(BaseModel):
    user_name: str
    git_url: str
    base_branch: str
    feature_branch: str


class SessionOut(BaseModel):
    id: str
    user_name: str
    git_url: str
    base_branch: str
    feature_branch: str
    title: str
    status: str
    error: str
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
        created_at=s.created_at.isoformat(),
    )


def _get(s, sid: str, include_deleted: bool = False) -> SessionRow:
    row = s.get(SessionRow, sid)
    if row is None or (row.deleted and not include_deleted):
        raise HTTPException(status_code=404, detail="session not found")
    return row


_inflight: set[str] = set()


def _kick(sid: str, task) -> None:
    if sid in _inflight:
        return
    _inflight.add(sid)
    asyncio.get_running_loop().create_task(task(sid))


def _set_status(sid: str, status: str, error: str | None = None):
    def inner(s):
        row = s.get(SessionRow, sid)
        if row is None:
            return
        row.status = status
        if error is not None:
            row.error = error
        s.commit()

    return inner


def _mark_error(sid: str, msg: str):
    return _set_status(sid, "error", msg)


async def _workspace_task(sid: str, *, restore: bool) -> None:
    try:
        row = await db.run_db(lambda s: _get(s, sid) if restore else s.get(SessionRow, sid))
        restore_fn = None
        if restore:
            from app.services.snapshots import restore_artifacts

            restore_fn = restore_artifacts
        await workspace.ensure_workspace(row, restore_artifacts=restore_fn)
        await db.run_db(_set_status(sid, "ready", ""))
    except workspace.WorkspaceError as e:
        await db.run_db(_mark_error(sid, str(e)))
    except Exception as e:
        logger.exception("%s task failed sid=%s", "restore" if restore else "clone", sid)
        await db.run_db(_mark_error(sid, str(e)))
    finally:
        _inflight.discard(sid)


async def _clone_task(sid: str) -> None:
    await _workspace_task(sid, restore=False)


@router.post("", status_code=202)
async def create_session(body: SessionCreate):
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
            )
        )
        s.commit()

    await db.run_db(_insert)
    _kick(sid, _clone_task)
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
    row = await db.run_db(lambda s: _get(s, sid))
    if row.status == "ready" and not (workspace.repo_dir(sid) / ".git").exists():
        await db.run_db(_set_status(sid, "restoring"))
        _kick(sid, _restore_task)
        row = await db.run_db(lambda s: _get(s, sid))
    elif row.status == "cloning":
        _kick(sid, _clone_task)
    elif row.status == "restoring":
        _kick(sid, _restore_task)
    return _to_out(row)


async def _restore_task(sid: str) -> None:
    await _workspace_task(sid, restore=True)


@router.post("/{sid}/snapshots")
async def manual_snapshot(sid: str):
    await db.run_db(lambda s: _get(s, sid))
    from app.services.snapshots import take_snapshot

    n = await take_snapshot(sid, "manual")
    return {"files": n}


@router.delete("/{sid}", status_code=204)
async def delete_session(sid: str, purge: bool = Query(False)):
    await db.run_db(lambda s: _get(s, sid, include_deleted=True))

    def _soft(s):
        row = s.get(SessionRow, sid)
        row.deleted = True
        s.commit()

    await db.run_db(_soft)
    if purge:
        root = workspace.workspace_root(sid)
        if root.exists():
            await asyncio.to_thread(workspace._rmtree, root)

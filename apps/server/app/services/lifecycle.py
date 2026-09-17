"""会话生命周期：session 状态机与 agent 回合的唯一入口。

会话状态转移（cloning / ready / running / error / restoring）全部收在本模块：
路由只做 HTTP 参数解析，通过本模块的窄接口驱动状态机。
"""

import asyncio
import logging

from app import db
from app.db import SessionRow
from app.services import agent, mcp_oauth, workspace
from app.services.bus import bus
from app.services.claude_runtime import current_git_auth

logger = logging.getLogger(__name__)


class SessionNotFound(Exception):
    """会话不存在或已删除。"""


class TurnConflict(Exception):
    """回合无法开始（agent 在跑 / 状态不是 ready / OAuth 未完成）。"""

    def __init__(self, message: str, *, payload=None):
        super().__init__(message)
        self.payload = payload


async def get_session(sid: str, *, include_deleted: bool = False) -> SessionRow:
    row = await db.run_db(lambda s: s.get(SessionRow, sid))
    if row is None or (row.deleted and not include_deleted):
        raise SessionNotFound(sid)
    return row


async def _set_status(sid: str, status: str, error: str | None = None) -> None:
    def write(s):
        row = s.get(SessionRow, sid)
        if row is None:
            return
        row.status = status
        if error is not None:
            row.error = error
        s.commit()

    await db.run_db(write)


async def _claim_running(sid: str) -> bool:
    """原子抢占 ready→running：单条条件 UPDATE，0 行命中即并发输了。"""

    def write(s):
        updated = (
            s.query(SessionRow)
            .filter(SessionRow.id == sid, SessionRow.status == "ready")
            .update({"status": "running"}, synchronize_session=False)
        )
        s.commit()
        return updated == 1

    return await db.run_db(write)


async def begin_turn(sid: str, user_text: str) -> None:
    """开始一个 agent 回合：校验 → 置 running → 落库并广播用户消息 → 后台驱动回合。

    成功返回时后台任务已创建（调用方无需再管 run_agent_turn 的调度）。
    """
    row = await get_session(sid)
    if agent.turn_active(sid):
        raise TurnConflict("agent is running")
    if row.status != "ready":
        raise TurnConflict(f"session status is {row.status}")
    missing = await asyncio.to_thread(mcp_oauth.missing_oauth_servers, row.user_name)
    if missing:
        raise TurnConflict(
            "mcp oauth required",
            payload={"code": "mcp_oauth_required", "servers": missing},
        )
    if not await _claim_running(sid):
        raise TurnConflict("session is starting a turn")
    await bus.publish(
        sid,
        {
            "type": "agent_message",
            "role": "user",
            "blocks": [{"kind": "text", "text": user_text}],
        },
    )
    await agent.save_message(sid, "user", [{"kind": "text", "text": user_text}])
    asyncio.get_running_loop().create_task(agent.run_agent_turn(sid, user_text))


async def turn_failed(sid: str, error: str) -> None:
    """回合异常：广播 agent_error（状态由 turn_finished 收尾回 ready）。"""
    await bus.publish(sid, {"type": "agent_error", "message": error})


async def turn_finished(sid: str) -> None:
    """回合收尾：置回 ready、落盘 CLI transcript、触发快照。"""
    await _set_status(sid, "ready")
    try:
        await _persist_cli_session(sid)
    except Exception:  # noqa: BLE001
        logger.exception("persist claude transcript failed")
    try:
        from app.services.snapshots import take_snapshot

        await take_snapshot(sid, "agent_done")
    except Exception:  # noqa: BLE001
        logger.exception("snapshot after agent turn failed")


async def _persist_cli_session(session_id: str) -> None:
    def read_id(s2):
        row = s2.get(SessionRow, session_id)
        return row.claude_session_id if row else None

    cid = await db.run_db(read_id)
    if not cid:
        return
    from app.services.claude_runtime import get_runtime

    transcript, tasks = await asyncio.to_thread(get_runtime().dump_cli_session, cid)
    if transcript is None and tasks is None:
        return

    def write(s2):
        row = s2.get(SessionRow, session_id)
        if not row:
            return
        if transcript is not None:
            row.claude_transcript = transcript
        if tasks is not None:
            row.claude_tasks = tasks
        s2.commit()

    await db.run_db(write)


# ---- 工作区（clone / restore）的后台任务与 in-flight 保护 ----

_inflight: set[str] = set()


def _kick(sid: str, task) -> None:
    if sid in _inflight:
        return
    _inflight.add(sid)
    asyncio.get_running_loop().create_task(task(sid))


def kick_clone(sid: str) -> None:
    _kick(sid, _clone_task)


def kick_restore(sid: str) -> None:
    _kick(sid, _restore_task)


async def _workspace_task(sid: str, *, restore: bool) -> None:
    try:
        if restore:
            row = await get_session(sid)
            from app.services.snapshots import restore_artifacts

            restore_fn = restore_artifacts
        else:
            row = await db.run_db(lambda s: s.get(SessionRow, sid))
            restore_fn = None
        token, username = current_git_auth()
        await workspace.ensure_workspace(
            row, restore_artifacts=restore_fn, token=token, username=username
        )
        await _set_status(sid, "ready", "")
    except workspace.WorkspaceError as e:
        await _set_status(sid, "error", str(e))
    except Exception as e:  # noqa: BLE001
        logger.exception("%s task failed sid=%s", "restore" if restore else "clone", sid)
        await _set_status(sid, "error", str(e))
    finally:
        _inflight.discard(sid)


async def _clone_task(sid: str) -> None:
    await _workspace_task(sid, restore=False)


async def _restore_task(sid: str) -> None:
    await _workspace_task(sid, restore=True)


async def rehydrate(row: SessionRow) -> SessionRow:
    """GET 详情时的自愈：repo 丢了转 restoring；卡在 cloning/restoring 的重新 kick。"""
    sid = row.id
    if row.status == "ready" and not (workspace.repo_dir(sid) / ".git").exists():
        await _set_status(sid, "restoring")
        _kick(sid, _restore_task)
        row = await get_session(sid)
    elif row.status == "cloning":
        _kick(sid, _clone_task)
    elif row.status == "restoring":
        _kick(sid, _restore_task)
    return row

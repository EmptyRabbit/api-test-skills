import asyncio

import pytest

from app.db import SessionRow
from app.services import agent, lifecycle


@pytest.fixture
async def ready_session(settings):
    from app import db as db_mod

    db_mod.init_engine(settings.database_url, settings.data_dir)
    row = SessionRow(
        id="s-lc",
        user_name="alice",
        git_url="http://example.invalid/x.git",
        base_branch="master",
        feature_branch="feature/x",
        status="ready",
    )
    await db_mod.run_db(lambda s: (s.add(row), s.commit()))
    return row.id


async def _status(sid: str) -> str:
    from app import db as db_mod

    return await db_mod.run_db(lambda s: s.get(SessionRow, sid).status)


async def test_get_session_missing_raises(settings):
    from app import db as db_mod

    db_mod.init_engine(settings.database_url, settings.data_dir)
    with pytest.raises(lifecycle.SessionNotFound):
        await lifecycle.get_session("nope")


async def test_begin_turn_conflict_when_turn_active(ready_session, monkeypatch):
    monkeypatch.setattr(agent, "turn_active", lambda _sid: True)
    with pytest.raises(lifecycle.TurnConflict, match="agent is running"):
        await lifecycle.begin_turn(ready_session, "hi")


async def test_begin_turn_conflict_when_not_ready(settings):
    from app import db as db_mod

    db_mod.init_engine(settings.database_url, settings.data_dir)
    row = SessionRow(
        id="s-clone",
        user_name="alice",
        git_url="http://example.invalid/x.git",
        base_branch="master",
        feature_branch="feature/x",
        status="cloning",
    )
    await db_mod.run_db(lambda s: (s.add(row), s.commit()))
    with pytest.raises(lifecycle.TurnConflict, match="session status is cloning"):
        await lifecycle.begin_turn("s-clone", "hi")


async def test_begin_turn_conflict_when_oauth_missing(ready_session, monkeypatch):
    from app.services import mcp_oauth

    monkeypatch.setattr(mcp_oauth, "missing_oauth_servers", lambda _u: ["mcp-a"])
    with pytest.raises(lifecycle.TurnConflict) as ei:
        await lifecycle.begin_turn(ready_session, "hi")
    assert ei.value.payload == {"code": "mcp_oauth_required", "servers": ["mcp-a"]}


async def test_begin_turn_launches_turn(ready_session, monkeypatch):
    from app import db as db_mod
    from app.db import MessageRow
    from app.services import mcp_oauth
    from app.services.bus import bus

    monkeypatch.setattr(mcp_oauth, "missing_oauth_servers", lambda _u: [])
    started: list[tuple[str, str]] = []

    async def fake_run(sid, text, *, make_client=None):
        started.append((sid, text))

    monkeypatch.setattr(agent, "run_agent_turn", fake_run)
    q = bus.subscribe(ready_session)
    try:
        await lifecycle.begin_turn(ready_session, "第一句")
        await asyncio.sleep(0.05)
        assert started == [(ready_session, "第一句")]
        assert await _status(ready_session) == "running"
        ev = q.get_nowait()
        assert ev["role"] == "user"
        roles = await db_mod.run_db(
            lambda s: [
                m.role for m in s.query(MessageRow).filter_by(session_id=ready_session)
            ]
        )
        assert roles == ["user"]
    finally:
        bus.unsubscribe(ready_session, q)


async def test_turn_finished_resets_ready_and_snapshots(ready_session, monkeypatch):
    from app import db as db_mod
    from app.services import snapshots

    def set_running(s):
        row = s.get(SessionRow, "s-lc")
        row.status = "running"
        s.commit()

    await db_mod.run_db(set_running)
    persisted: list[str] = []
    snapped: list[tuple[str, str]] = []

    async def fake_persist(sid):
        persisted.append(sid)

    async def fake_snap(sid, trigger):
        snapped.append((sid, trigger))

    monkeypatch.setattr(lifecycle, "_persist_cli_session", fake_persist)
    monkeypatch.setattr(snapshots, "take_snapshot", fake_snap)
    await lifecycle.turn_finished(ready_session)
    assert persisted == [ready_session]
    assert snapped == [(ready_session, "agent_done")]
    assert await _status(ready_session) == "ready"


async def test_rehydrate_marks_restoring_when_repo_lost(
    ready_session, settings, monkeypatch
):
    from app.services import workspace

    monkeypatch.setattr(workspace, "_data_dir", settings.data_dir)
    kicks: list[tuple[str, str]] = []

    async def fake_task(sid, *, restore):
        kicks.append(("restore" if restore else "clone", sid))

    monkeypatch.setattr(lifecycle, "_workspace_task", fake_task)
    row = await lifecycle.get_session(ready_session)
    row = await lifecycle.rehydrate(row)
    await asyncio.sleep(0.05)
    assert row.status == "restoring"
    assert kicks == [("restore", ready_session)]


async def test_kick_clone_dedupes_inflight(monkeypatch):
    calls: list[str] = []

    async def fake_task(sid, *, restore):
        calls.append(sid)

    monkeypatch.setattr(lifecycle, "_workspace_task", fake_task)
    lifecycle.kick_clone("s-x")
    lifecycle.kick_clone("s-x")
    await asyncio.sleep(0.05)
    assert calls.count("s-x") == 1
    lifecycle._inflight.discard("s-x")


async def test_begin_turn_conflict_when_race_flips_status(ready_session, monkeypatch):
    from app import db as db_mod
    from app.services import mcp_oauth

    def racing_missing(user_name):
        # 模拟并发赢家：在 oauth 检查的线程里把状态抢先翻到 running
        with db_mod.SessionLocal() as s:
            row = s.get(SessionRow, ready_session)
            row.status = "running"
            s.commit()
        return []

    monkeypatch.setattr(mcp_oauth, "missing_oauth_servers", racing_missing)
    with pytest.raises(lifecycle.TurnConflict, match="starting a turn"):
        await lifecycle.begin_turn(ready_session, "hi")


async def test_workspace_task_passes_git_auth(ready_session, monkeypatch):
    from app.services import workspace

    seen: dict = {}

    async def fake_ensure(session, restore_artifacts=None, *, token=None, username="oauth2"):
        seen["token"] = token
        seen["username"] = username

    monkeypatch.setattr(lifecycle, "current_git_auth", lambda: ("tok-9", "gl"))
    monkeypatch.setattr(workspace, "ensure_workspace", fake_ensure)
    await lifecycle._workspace_task(ready_session, restore=False)
    assert seen == {"token": "tok-9", "username": "gl"}
    assert await _status(ready_session) == "ready"

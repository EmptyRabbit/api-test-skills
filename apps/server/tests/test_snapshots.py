import pytest

from app.services import snapshots, workspace


@pytest.fixture
def sid(settings, monkeypatch):
    from app import db as db_mod

    monkeypatch.setattr(workspace, "_data_dir", settings.data_dir)
    db_mod.init_engine(settings.database_url, settings.data_dir)
    workspace.artifacts_dir("s-snap").mkdir(parents=True, exist_ok=True)
    return "s-snap"


async def test_take_and_restore_roundtrip(sid):
    art = workspace.artifacts_dir(sid)
    (art / "docs").mkdir(exist_ok=True)
    (art / "docs" / "00-context.md").write_text("# ctx", encoding="utf-8")
    (art / "test_case.py").write_text("def test_x():\n    pass\n", encoding="utf-8")
    (art / "__pycache__").mkdir(exist_ok=True)
    (art / "__pycache__" / "junk.pyc").write_bytes(b"\x00\x01")

    n = await snapshots.take_snapshot(sid, "agent_done")
    assert n == 2  # pyc 被跳过

    # 磁盘被清后恢复
    import shutil

    shutil.rmtree(art)
    assert await snapshots.restore_artifacts(sid) is True
    assert (art / "docs" / "00-context.md").read_text(encoding="utf-8") == "# ctx"
    assert (art / "test_case.py").exists()
    assert not (art / "__pycache__").exists()


async def test_snapshot_overwrites_previous(sid):
    art = workspace.artifacts_dir(sid)
    (art / "a.md").write_text("v1", encoding="utf-8")
    await snapshots.take_snapshot(sid, "agent_done")
    (art / "a.md").write_text("v2", encoding="utf-8")
    await snapshots.take_snapshot(sid, "agent_done")

    from app import db
    from app.db import SnapshotRow

    def count(s):
        return s.query(SnapshotRow).filter_by(session_id=sid).count()

    assert await db.run_db(count) == 1


async def test_restore_without_snapshot(sid):
    import shutil

    shutil.rmtree(workspace.artifacts_dir(sid), ignore_errors=True)
    workspace.artifacts_dir(sid).mkdir(parents=True, exist_ok=True)
    assert await snapshots.restore_artifacts(sid) is False

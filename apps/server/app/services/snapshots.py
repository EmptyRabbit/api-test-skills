import asyncio
import os

from app import db
from app.db import SnapshotFileRow, SnapshotRow
from app.services import workspace

SKIP_DIRS = {"__pycache__", ".pytest_cache", ".git", "node_modules", ".venv"}


def _iter_text_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in sorted(filenames):
            p = os.path.join(dirpath, name)
            try:
                with open(p, encoding="utf-8") as f:
                    text = f.read()
            except (UnicodeDecodeError, ValueError, OSError):
                continue
            rel = os.path.relpath(p, root).replace("\\", "/")
            yield rel, text


async def take_snapshot(session_id: str, trigger: str) -> int:
    art = workspace.artifacts_dir(session_id)

    def collect():
        if not art.exists():
            return []
        return list(_iter_text_files(art))

    files = await asyncio.to_thread(collect)

    def write(s):
        old_ids = [
            r.id for r in s.query(SnapshotRow).filter_by(session_id=session_id)
        ]
        if old_ids:
            s.query(SnapshotFileRow).filter(
                SnapshotFileRow.snapshot_id.in_(old_ids)
            ).delete(synchronize_session=False)
            s.query(SnapshotRow).filter(SnapshotRow.id.in_(old_ids)).delete(
                synchronize_session=False
            )
        row = SnapshotRow(session_id=session_id, trigger=trigger)
        s.add(row)
        s.flush()
        for path, content in files:
            s.add(SnapshotFileRow(snapshot_id=row.id, path=path, content=content))
        s.commit()

    await db.run_db(write)
    return len(files)


async def restore_artifacts(session_id: str) -> bool:
    def read(s):
        snap = (
            s.query(SnapshotRow)
            .filter_by(session_id=session_id)
            .order_by(SnapshotRow.id.desc())
            .first()
        )
        if snap is None:
            return None
        return [
            (f.path, f.content)
            for f in s.query(SnapshotFileRow).filter_by(snapshot_id=snap.id)
        ]

    files = await db.run_db(read)
    if files is None:
        return False
    art = workspace.artifacts_dir(session_id)
    art.mkdir(parents=True, exist_ok=True)
    for path, content in files:
        target = art / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return True

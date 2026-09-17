import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services import lifecycle, workspace
from app.services.snapshots import SKIP_DIRS

router = APIRouter(prefix="/api/sessions", tags=["files"])


def _safe_path(sid: str, rel: str) -> Path:
    root = workspace.workspace_root(sid).resolve()
    p = (root / rel).resolve()
    try:
        p.relative_to(root)
    except ValueError:
        raise HTTPException(status_code=403, detail="path outside workspace")
    return p


@router.get("/{sid}/files/tree")
async def tree(sid: str, path: str = Query("")):
    await lifecycle.get_session(sid)

    root = workspace.workspace_root(sid).resolve()
    base = _safe_path(sid, path)
    if not base.is_dir():
        raise HTTPException(status_code=404, detail="not a directory")

    def listdir():
        out = []
        for child in sorted(base.iterdir(), key=lambda c: (c.is_file(), c.name.lower())):
            if child.name in SKIP_DIRS:
                continue
            rel = child.relative_to(root).as_posix()
            out.append(
                {
                    "name": child.name,
                    "path": rel,
                    "type": "dir" if child.is_dir() else "file",
                    "size": child.stat().st_size if child.is_file() else 0,
                }
            )
        return out

    return await asyncio.to_thread(listdir)


@router.get("/{sid}/files/content")
async def read_file(sid: str, path: str = Query(...)):
    await lifecycle.get_session(sid)

    p = _safe_path(sid, path)
    if not p.is_file():
        raise HTTPException(status_code=404, detail="file not found")

    def read():
        try:
            return p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raise HTTPException(status_code=415, detail="binary file not supported")

    return {"path": path, "content": await asyncio.to_thread(read)}


class FileWrite(BaseModel):
    path: str
    content: str


@router.put("/{sid}/files/content")
async def write_file(sid: str, body: FileWrite):
    await lifecycle.get_session(sid)

    p = _safe_path(sid, body.path)

    def write():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body.content, encoding="utf-8")

    await asyncio.to_thread(write)
    return {"ok": True}

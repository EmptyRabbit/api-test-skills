import asyncio
import os
import stat
import subprocess
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

from app.config import get_settings
from app.db import SessionRow
from app.windows_loop import hidden_popen_kwargs


def _fs_path(path: Path | str) -> str:
    """Absolute path for shutil/os. Windows gets the \\\\?\\ prefix (MAX_PATH); POSIX is unchanged."""
    p = os.path.abspath(os.fspath(path))
    if os.name != "nt":
        return p
    if p.startswith("\\\\?\\"):
        return p
    if p.startswith("\\\\"):
        return "\\\\?\\UNC\\" + p[2:]
    return "\\\\?\\" + p


def _make_writable(p: str) -> None:
    # POSIX: OR in owner rwx so directories keep search/execute. Windows: clears readonly.
    mode = os.stat(p).st_mode
    os.chmod(p, mode | stat.S_IWUSR | stat.S_IRUSR | stat.S_IXUSR)


def _rmtree(path: Path) -> None:
    """Delete a tree on Windows/Linux/macOS (readonly git files, unwritable dirs, long paths)."""
    import shutil

    def _onerror(func, p, exc_info):
        if isinstance(exc_info[1], FileNotFoundError):
            return
        # POSIX unlink needs the parent dir writable; Windows often needs the file itself.
        for target in (p, os.path.dirname(p)):
            if not target:
                continue
            try:
                _make_writable(target)
            except FileNotFoundError:
                return
        try:
            func(p)
        except FileNotFoundError:
            return

    shutil.rmtree(_fs_path(path), onerror=_onerror)


class WorkspaceError(Exception):
    pass


_data_dir: Path | None = None


def _dir() -> Path:
    global _data_dir
    if _data_dir is None:
        _data_dir = get_settings().data_dir
    return _data_dir


def workspace_root(session_id: str) -> Path:
    return _dir() / "workspaces" / session_id


def repo_dir(session_id: str) -> Path:
    return workspace_root(session_id) / "repo"


def artifacts_dir(session_id: str) -> Path:
    return workspace_root(session_id) / "artifacts"


def _redact(text: str, secrets: tuple[str, ...]) -> str:
    out = text
    for secret in secrets:
        if not secret:
            continue
        out = out.replace(secret, "***")
        encoded = quote(secret, safe="")
        if encoded != secret:
            out = out.replace(encoded, "***")
    return out


def _http_host(parts) -> str:
    host = parts.hostname or ""
    return f"{host}:{parts.port}" if parts.port else host


def inject_git_token(git_url: str, token: str | None, username: str = "oauth2") -> str:
    """Rewrite http(s) clone URLs with Basic-auth token. Leave SSH/local/already-authed URLs alone."""
    if not token:
        return git_url
    parts = urlsplit(git_url)
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username:
        return git_url
    netloc = f"{quote(username, safe='')}:{quote(token, safe='')}@{_http_host(parts)}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def _http_prefix(git_url: str) -> str | None:
    parts = urlsplit(git_url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return None
    return f"{parts.scheme}://{_http_host(parts)}/"


async def _git(
    args: list[str], cwd: Path | None = None, *, redact: tuple[str, ...] = ()
) -> str:
    # Windows 上 uvicorn 常用 SelectorEventLoop，create_subprocess_exec 会 NotImplementedError
    def _run() -> tuple[int, str]:
        kw: dict = {
            "args": ["git", *args],
            "cwd": cwd,
            "capture_output": True,
            "text": True,
            "errors": "replace",
            **hidden_popen_kwargs(),
        }
        proc = subprocess.run(**kw)
        out = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode, out

    code, text = await asyncio.to_thread(_run)
    if code != 0:
        msg = _redact(f"git {' '.join(args)} failed: {text.strip()}", redact)
        raise WorkspaceError(msg)
    return text


async def clone_repo(
    git_url: str,
    feature_branch: str,
    dest: Path,
    *,
    token: str | None = None,
    username: str = "oauth2",
) -> None:
    """凭据由调用方显式注入；不传 token 则按无凭据 clone（本地/SSH 地址）。"""
    dest.parent.mkdir(parents=True, exist_ok=True)
    secrets = (token,) if token else ()
    clone_url = inject_git_token(git_url, token, username)
    await _git(
        ["clone", "--branch", feature_branch, clone_url, str(dest)],
        redact=secrets,
    )
    if token and clone_url != git_url:
        await _git(["remote", "set-url", "origin", git_url], cwd=dest, redact=secrets)
        origin = _http_prefix(git_url)
        if origin:
            authed = inject_git_token(origin, token, username)
            await _git(
                ["config", "--local", f"url.{authed}.insteadOf", origin],
                cwd=dest,
                redact=secrets,
            )


async def ensure_workspace(
    session: SessionRow,
    restore_artifacts=None,
    *,
    token: str | None = None,
    username: str = "oauth2",
) -> None:
    """repo 缺失重 clone；artifacts 缺失/为空时用 restore_artifacts(sid) 回填。"""
    sid = session.id
    repo = repo_dir(sid)
    if not (repo / ".git").exists():
        if repo.exists():
            _rmtree(repo)
        await clone_repo(
            session.git_url, session.feature_branch, repo, token=token, username=username
        )

    art = artifacts_dir(sid)
    art.mkdir(parents=True, exist_ok=True)
    if not any(art.iterdir()) and restore_artifacts is not None:
        await restore_artifacts(sid)

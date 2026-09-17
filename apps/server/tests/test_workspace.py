import subprocess
from pathlib import Path

import pytest

from app.services import workspace


def _git(args, cwd):
    subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True
    )


@pytest.fixture
def origin_repo(tmp_path):
    origin = tmp_path / "origin"
    origin.mkdir()
    _git(["init", "-b", "master"], origin)
    _git(["config", "user.email", "t@t"], origin)
    _git(["config", "user.name", "t"], origin)
    (origin / "README.md").write_text("# hello")
    _git(["add", "."], origin)
    _git(["commit", "-m", "init"], origin)
    _git(["checkout", "-b", "feature/x"], origin)
    (origin / "app.py").write_text("print('feature')\n")
    _git(["add", "."], origin)
    _git(["commit", "-m", "feat"], origin)
    _git(["checkout", "master"], origin)
    return origin


def test_inject_git_token_https_only():
    token = "s3cret/token"
    assert (
        workspace.inject_git_token("https://gitlab.example/g/r.git", token)
        == "https://oauth2:s3cret%2Ftoken@gitlab.example/g/r.git"
    )
    assert (
        workspace.inject_git_token("http://git.example:8080/r.git", token, "gl")
        == "http://gl:s3cret%2Ftoken@git.example:8080/r.git"
    )
    already = "https://oauth2:old@gitlab.example/g/r.git"
    assert workspace.inject_git_token(already, token) == already
    assert workspace.inject_git_token("/tmp/origin", token) == "/tmp/origin"
    assert workspace.inject_git_token("git@gitlab.example:g/r.git", token) == "git@gitlab.example:g/r.git"
    assert workspace.inject_git_token("https://gitlab.example/g/r.git", None) == "https://gitlab.example/g/r.git"


def test_inject_git_token_local_windows_path():
    path = r"D:\repos\origin"
    assert workspace.inject_git_token(path, "tok") == path


async def test_clone_repo_rewrites_https_and_sets_instead_of(tmp_path, monkeypatch):
    seen: list[tuple[list[str], str | None]] = []

    async def fake_git(args, cwd=None, *, redact=()):
        seen.append((list(args), str(cwd) if cwd else None))
        if args[0] == "clone":
            dest = Path(args[-1])
            dest.mkdir(parents=True)
            (dest / ".git").mkdir()
        return ""

    monkeypatch.setattr(workspace, "_git", fake_git)
    monkeypatch.setattr(workspace, "_git_auth", lambda: ("s3cret", "oauth2"))
    dest = tmp_path / "repo"
    url = "https://gitlab.example/g/r.git"
    await workspace.clone_repo(url, "feature/x", dest)
    assert seen[0][0] == [
        "clone",
        "--branch",
        "feature/x",
        "https://oauth2:s3cret@gitlab.example/g/r.git",
        str(dest),
    ]
    assert seen[1][0] == ["remote", "set-url", "origin", url]
    assert seen[2][0] == [
        "config",
        "--local",
        "url.https://oauth2:s3cret@gitlab.example/.insteadOf",
        "https://gitlab.example/",
    ]


async def test_clone_error_redacts_token(monkeypatch):
    async def boom(args, cwd=None, *, redact=()):
        raise workspace.WorkspaceError(
            workspace._redact(
                f"git {' '.join(args)} failed: fatal: {args[2]}",
                redact,
            )
        )

    monkeypatch.setattr(workspace, "_git", boom)
    monkeypatch.setattr(workspace, "_git_auth", lambda: ("s3cret", "oauth2"))
    with pytest.raises(workspace.WorkspaceError) as ei:
        await workspace.clone_repo("https://gitlab.example/g/r.git", "main", Path("/tmp/x"))
    assert "s3cret" not in str(ei.value)


async def test_clone_repo_checks_out_feature(origin_repo, tmp_path):
    dest = tmp_path / "repo"
    await workspace.clone_repo(str(origin_repo), "feature/x", dest)
    assert (dest / "app.py").read_text() == "print('feature')\n"
    assert (dest / ".git").exists()


async def test_clone_repo_bad_branch_raises(origin_repo, tmp_path):
    with pytest.raises(workspace.WorkspaceError):
        await workspace.clone_repo(str(origin_repo), "no-such-branch", tmp_path / "r2")


async def test_ensure_workspace_reclones_missing_repo(
    origin_repo, tmp_path, monkeypatch
):
    monkeypatch.setattr(workspace, "_data_dir", tmp_path)
    sid = "s-1"
    from app.db import SessionRow

    s = SessionRow(
        id=sid,
        user_name="u",
        git_url=str(origin_repo),
        base_branch="master",
        feature_branch="feature/x",
    )
    await workspace.ensure_workspace(s, restore_artifacts=None)
    assert (workspace.repo_dir(sid) / "app.py").exists()
    assert workspace.artifacts_dir(sid).is_dir()

    # 磁盘被清（删 workspace）后再次 ensure 能恢复 repo
    import os
    import stat
    import shutil

    def _handle_readonly(func, p, exc_info):
        os.chmod(p, stat.S_IWRITE)
        func(p)

    shutil.rmtree(workspace.workspace_root(sid), onerror=_handle_readonly)
    await workspace.ensure_workspace(s, restore_artifacts=None)
    assert (workspace.repo_dir(sid) / "app.py").exists()

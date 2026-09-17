"""Materialize an isolated Claude Code home for the platform process."""

from __future__ import annotations

import json
import logging
import os
import shutil
from pathlib import Path

import yaml

from app.config import Settings
from app.platform_config import PlatformConfigError, PlatformFile, load_platform_file

logger = logging.getLogger(__name__)

_runtime: ClaudeRuntime | None = None


def claude_project_dir_name(cwd: Path) -> str:
    return str(cwd.resolve()).replace(":", "-").replace("\\", "-").replace("/", "-")


def _rm(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
        return
    if path.is_dir():
        shutil.rmtree(path)


def _link_dir(src: Path, dest: Path) -> None:
    """Point dest at src via a real reference (symlink / junction).

    Never falls back to copying: skills must always be a live reference to
    skill_roots, so edits at the source show up immediately and there's no
    stale duplicate content to go out of sync.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() or dest.is_symlink():
        _rm(dest)
    try:
        dest.symlink_to(src, target_is_directory=True)
        return
    except OSError as exc:
        symlink_err = exc
    if os.name == "nt":
        import subprocess

        from app.windows_loop import hidden_popen_kwargs

        r = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(dest), str(src)],
            capture_output=True,
            text=True,
            **hidden_popen_kwargs(),
        )
        if r.returncode == 0:
            return
        raise PlatformConfigError(
            f"无法为 skill 创建引用 {dest} -> {src}："
            f"符号链接失败({symlink_err})，目录联接(mklink /J)也失败："
            f"{r.stderr.strip() or r.stdout.strip()}"
        ) from symlink_err
    raise PlatformConfigError(
        f"无法为 skill 创建符号链接 {dest} -> {src}：{symlink_err}"
    ) from symlink_err


def _iter_skills(root: Path) -> list[tuple[str, Path]]:
    if (root / "SKILL.md").is_file():
        return [(root.name, root)]
    found: list[tuple[str, Path]] = []
    for child in sorted(root.iterdir()):
        if child.is_dir() and (child / "SKILL.md").is_file():
            found.append((child.name, child))
    return found


def _model_env(m) -> dict[str, str]:
    env: dict[str, str] = {}
    if m.base_url:
        env["ANTHROPIC_BASE_URL"] = m.base_url
    if m.auth_token:
        env["ANTHROPIC_AUTH_TOKEN"] = m.auth_token
    return env


class ClaudeRuntime:
    def __init__(self, spec: PlatformFile):
        self.spec = spec

    @property
    def mcp_servers(self) -> dict:
        return self.spec.mcp_servers

    @property
    def cli_env(self) -> dict[str, str]:
        m = self.spec.model
        env = {
            "CLAUDE_CONFIG_DIR": str(self.spec.claude_home),
            **_model_env(m),
        }
        if m.name:
            env["ANTHROPIC_CUSTOM_MODEL_OPTION"] = m.name
        if os.name != "nt":
            env["HOME"] = str(self.spec.claude_home)
        return env

    def _vendor_yaml(self) -> str:
        return yaml.safe_dump({"vendor": self.spec.vendor}, allow_unicode=True)

    def materialize(self) -> None:
        home = self.spec.claude_home
        skills_dir = home / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        names: dict[str, Path] = {}
        for root in self.spec.skill_roots:
            for name, src in _iter_skills(root):
                if name in names:
                    raise RuntimeError(
                        f"skill 名称冲突: {name} 同时来自 {names[name]} 和 {src}"
                    )
                names[name] = src
                _link_dir(src, skills_dir / name)

        settings: dict = {
            "permissions": {
                "defaultMode": "bypassPermissions",
                "allowedModes": [
                    "default",
                    "acceptEdits",
                    "plan",
                    "bypassPermissions",
                ],
            },
            "enabledPlugins": {},
            "hooks": {},
        }
        if self.spec.model.name:
            settings["model"] = self.spec.model.name
        env_block = _model_env(self.spec.model)
        if env_block:
            settings["env"] = env_block
        (home / "settings.json").write_text(
            json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (home / ".api-test-skills.yaml").write_text(self._vendor_yaml(), encoding="utf-8")
        logger.info(
            "claude home %s skills=%s mcp=%s vendor=%s source=%s",
            home,
            sorted(names),
            sorted(self.spec.mcp_servers),
            self.spec.vendor,
            self.spec.source,
        )

    def install_session_files(self, workspace_root: Path) -> None:
        workspace_root.mkdir(parents=True, exist_ok=True)
        dest = workspace_root / ".api-test-skills.yaml"
        text = self._vendor_yaml()
        if dest.is_file() and dest.read_text(encoding="utf-8") == text:
            return
        dest.write_text(text, encoding="utf-8")

    def cli_transcript_path(self, workspace_root: Path, claude_session_id: str) -> Path:
        return (
            self.spec.claude_home
            / "projects"
            / claude_project_dir_name(workspace_root)
            / f"{claude_session_id}.jsonl"
        )

    def _cli_tasks_dir(self, claude_session_id: str) -> Path:
        return self.spec.claude_home / "tasks" / claude_session_id

    def _find_cli_transcript(self, claude_session_id: str) -> Path | None:
        root = self.spec.claude_home / "projects"
        if not root.is_dir():
            return None
        return next(root.glob(f"*/{claude_session_id}.jsonl"), None)

    def dump_cli_session(
        self, claude_session_id: str
    ) -> tuple[str | None, dict[str, str] | None]:
        src = self._find_cli_transcript(claude_session_id)
        transcript = src.read_text(encoding="utf-8") if src and src.is_file() else None
        tasks_dir = self._cli_tasks_dir(claude_session_id)
        tasks: dict[str, str] = {}
        if tasks_dir.is_dir():
            tasks = {
                child.name: child.read_text(encoding="utf-8")
                for child in tasks_dir.iterdir()
                if child.is_file() and child.suffix == ".json"
            }
        return transcript, tasks or None

    def restore_cli_session(
        self,
        workspace_root: Path,
        claude_session_id: str,
        transcript: str | None,
        tasks: dict | None,
    ) -> bool:
        dest = self.cli_transcript_path(workspace_root, claude_session_id)
        if transcript and not dest.is_file():
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(transcript, encoding="utf-8")
        tasks_dest = self._cli_tasks_dir(claude_session_id)
        if tasks and not tasks_dest.exists():
            tasks_dest.mkdir(parents=True, exist_ok=True)
            for name, body in tasks.items():
                if Path(name).name != name or name in {".", ".."}:
                    continue
                (tasks_dest / name).write_text(str(body), encoding="utf-8")
        return dest.is_file()


def prepare_runtime(settings: Settings) -> ClaudeRuntime:
    global _runtime
    spec = load_platform_file(settings)
    rt = ClaudeRuntime(spec)
    rt.materialize()
    _runtime = rt
    return rt


def get_runtime() -> ClaudeRuntime:
    if _runtime is None:
        from app.config import get_settings

        return prepare_runtime(get_settings())
    return _runtime


def reset_runtime() -> None:
    global _runtime
    _runtime = None


def current_git_auth() -> tuple[str | None, str]:
    if _runtime is None:
        return None, "oauth2"
    return _runtime.spec.git.token, _runtime.spec.git.username

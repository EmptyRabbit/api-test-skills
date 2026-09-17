"""Load process-level platform.yaml (MCP / skills / Claude home). Isolated from ~/.claude."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from app.config import Settings

_VAR = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
_SERVER_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = Path(__file__).resolve().parents[3]


class PlatformConfigError(Exception):
    pass


@dataclass
class ModelConfig:
    name: str | None = None
    base_url: str | None = None
    auth_token: str | None = None


@dataclass
class GitConfig:
    token: str | None = None
    username: str = "oauth2"


@dataclass
class OAuthConfig:
    identity_claims: list[str] = field(
        default_factory=lambda: [
            "email",
            "mail",
            "preferred_username",
            "sub",
            "name",
        ]
    )


@dataclass
class PlatformFile:
    claude_home: Path
    vendor: str = "none"
    skill_roots: list[Path] = field(default_factory=list)
    mcp_servers: dict[str, dict[str, Any]] = field(default_factory=dict)
    oauth: OAuthConfig = field(default_factory=OAuthConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    git: GitConfig = field(default_factory=GitConfig)
    source: Path | None = None


def interpolate(value: Any, env: dict[str, str] | None = None) -> Any:
    env = env if env is not None else dict(os.environ)

    if isinstance(value, str):
        def repl(m: re.Match[str]) -> str:
            key = m.group(1)
            got = env.get(key)
            if got is None or got == "":
                raise PlatformConfigError(
                    f"platform.yaml 引用了未设置的环境变量 ${{{key}}}"
                )
            return got

        return _VAR.sub(repl, value)
    if isinstance(value, dict):
        return {k: interpolate(v, env) for k, v in value.items()}
    if isinstance(value, list):
        return [interpolate(v, env) for v in value]
    return value


def resolve_config_path() -> Path | None:
    raw = os.environ.get("PLATFORM_CONFIG")
    if raw:
        path = Path(raw)
        if not path.is_file():
            raise PlatformConfigError(f"PLATFORM_CONFIG 不是文件: {path}")
        return path.resolve()
    for cand in (_SERVER_DIR / "platform.yaml", Path.cwd() / "platform.yaml"):
        if cand.is_file():
            return cand.resolve()
    return None


def _normalize_mcp(raw: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for name, cfg in (raw or {}).items():
        if not isinstance(cfg, dict):
            raise PlatformConfigError(f"mcp_servers.{name} 必须是 mapping")
        item = dict(cfg)
        kind = str(item.get("type") or "http")
        if kind in ("streamable-http", "streamable_http"):
            item["type"] = "http"
        elif kind in ("http", "sse", "stdio"):
            item["type"] = kind
        else:
            raise PlatformConfigError(f"mcp_servers.{name} 不支持 type={kind}")
        auth = str(item.get("auth") or "").strip().lower()
        if auth and auth != "oauth":
            raise PlatformConfigError(f"mcp_servers.{name} 不支持 auth={item.get('auth')}")
        if auth:
            item["auth"] = "oauth"
        elif "auth" in item:
            item.pop("auth")
        if item["type"] == "stdio":
            if not item.get("command"):
                raise PlatformConfigError(f"mcp_servers.{name} stdio 缺少 command")
        elif not item.get("url"):
            raise PlatformConfigError(f"mcp_servers.{name} 缺少 url")
        out[name] = item
    return out


def _normalize_git(raw: Any) -> GitConfig:
    if not raw:
        return GitConfig()
    if not isinstance(raw, dict):
        raise PlatformConfigError("git 必须是 mapping")
    token = raw.get("token")
    if token is not None:
        if not isinstance(token, str):
            raise PlatformConfigError("git.token 必须是字符串")
        token = token.strip() or None
    username = raw.get("username", "oauth2")
    if not isinstance(username, str) or not username.strip():
        raise PlatformConfigError("git.username 必须是非空字符串")
    return GitConfig(token=token, username=username.strip())


def _normalize_oauth(raw: Any) -> OAuthConfig:
    if not raw:
        return OAuthConfig()
    if not isinstance(raw, dict):
        raise PlatformConfigError("oauth 必须是 mapping")
    claims = raw.get("identity_claims")
    if claims is None:
        return OAuthConfig()
    if not isinstance(claims, list) or not claims or not all(
        isinstance(x, str) and x.strip() for x in claims
    ):
        raise PlatformConfigError("oauth.identity_claims 必须是非空字符串列表")
    return OAuthConfig(identity_claims=[x.strip() for x in claims])


def load_platform_file(settings: Settings, *, env: dict[str, str] | None = None) -> PlatformFile:
    path = resolve_config_path()
    default_home = (settings.data_dir / "claude-home").resolve()
    default_skills = _REPO_ROOT / "skills"

    if path is None:
        roots = [default_skills] if default_skills.is_dir() else []
        return PlatformFile(claude_home=default_home, skill_roots=roots, source=None)

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise PlatformConfigError("platform.yaml 根节点必须是 mapping")
    data = interpolate(data, env if env is not None else dict(os.environ))

    home_raw = data.get("claude_home")
    home = Path(home_raw) if home_raw else default_home
    if not home.is_absolute():
        home = (path.parent / home).resolve()

    roots: list[Path] = []
    listed = data.get("skill_roots")
    if listed is None:
        if default_skills.is_dir():
            roots.append(default_skills)
    else:
        if not isinstance(listed, list):
            raise PlatformConfigError("skill_roots 必须是列表")
        for item in listed:
            p = Path(str(item))
            if not p.is_absolute():
                p = (path.parent / p).resolve()
            else:
                p = p.resolve()
            if not p.is_dir():
                raise PlatformConfigError(f"skill_roots 不存在: {p}")
            roots.append(p)

    model_raw = data.get("model") or {}
    if not isinstance(model_raw, dict):
        raise PlatformConfigError("model 必须是 mapping")
    model = ModelConfig(
        name=model_raw.get("name"),
        base_url=model_raw.get("base_url"),
        auth_token=model_raw.get("auth_token"),
    )
    mcp = _normalize_mcp(data.get("mcp_servers") or {})
    vendor = str(data.get("vendor") or "none")
    return PlatformFile(
        claude_home=home,
        vendor=vendor,
        skill_roots=roots,
        mcp_servers=mcp,
        oauth=_normalize_oauth(data.get("oauth")),
        model=model,
        git=_normalize_git(data.get("git")),
        source=path,
    )

import shutil
from pathlib import Path

import pytest
import yaml

from app import db as db_mod
from app.config import Settings
from app.db import SessionRow
from app.platform_config import PlatformConfigError, interpolate, load_platform_file
from app.services import agent, workspace
from app.services.claude_runtime import prepare_runtime


def test_interpolate_nested_and_missing():
    env = {"A": "one", "B": "two"}
    got = interpolate({"url": "http://${A}", "headers": {"t": "${B}"}}, env)
    assert got["url"] == "http://one"
    assert got["headers"]["t"] == "two"
    with pytest.raises(PlatformConfigError, match="MISSING"):
        interpolate("${MISSING}", env)


def test_load_yaml_mcp_and_vendor(tmp_path, monkeypatch):
    skills = tmp_path / "skills" / "generate-api-tests"
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text("# x\n", encoding="utf-8")
    yml = tmp_path / "platform.yaml"
    yml.write_text(
        yaml.safe_dump(
            {
                "claude_home": str(tmp_path / "home"),
                "vendor": "ctrip",
                "skill_roots": [str(tmp_path / "skills")],
                "mcp_servers": {
                    "DOT": {
                        "type": "streamable-http",
                        "url": "http://${DOT_URL}",
                        "headers": {"x-token": "${DOT_TOKEN}"},
                    }
                },
                "model": {"name": "glm-5.3", "base_url": "http://gw", "auth_token": "tok"},
                "git": {"token": "${GIT_TOKEN}", "username": "oauth2"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("PLATFORM_CONFIG", str(yml))
    monkeypatch.setenv("DOT_URL", "dot.example")
    monkeypatch.setenv("DOT_TOKEN", "secret")
    monkeypatch.setenv("GIT_TOKEN", "glpat-xxx")
    monkeypatch.setattr("app.platform_config.resolve_config_path", lambda: yml)

    spec = load_platform_file(Settings(data_dir=tmp_path / "data"), env=dict(**{**__import__("os").environ}))
    assert spec.vendor == "ctrip"
    assert spec.mcp_servers["DOT"]["type"] == "http"
    assert spec.mcp_servers["DOT"]["url"] == "http://dot.example"
    assert spec.mcp_servers["DOT"]["headers"]["x-token"] == "secret"
    assert spec.git.token == "glpat-xxx"
    assert spec.git.username == "oauth2"


def test_materialize_links_skills_and_writes_settings(tmp_path, monkeypatch):
    root = tmp_path / "bundle"
    skill = root / "generate-api-tests"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("n", encoding="utf-8")
    spec_dir = tmp_path / "platform.yaml"
    spec_dir.write_text(
        yaml.safe_dump(
            {
                "claude_home": str(tmp_path / "home"),
                "vendor": "none",
                "skill_roots": [str(root)],
                "mcp_servers": {},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("app.platform_config.resolve_config_path", lambda: spec_dir)
    rt = prepare_runtime(Settings(data_dir=tmp_path / "data"))
    dest = tmp_path / "home" / "skills" / "generate-api-tests"
    assert dest.exists()
    assert (dest / "SKILL.md").is_file()
    settings = (tmp_path / "home" / "settings.json").read_text(encoding="utf-8")
    assert "enabledPlugins" in settings
    assert rt.cli_env["CLAUDE_CONFIG_DIR"] == str((tmp_path / "home").resolve())


def test_build_agent_options_isolated(tmp_path, monkeypatch, settings):
    monkeypatch.setattr("app.services.workspace._data_dir", settings.data_dir)
    prepare_runtime(settings)
    row = SessionRow(
        id="s-iso",
        user_name="u",
        git_url="http://g/x.git",
        base_branch="master",
        feature_branch="f",
    )
    kwargs = agent.build_agent_options(row, settings)
    from claude_agent_sdk import ClaudeAgentOptions

    ClaudeAgentOptions(**kwargs)
    assert kwargs["strict_mcp_config"] is True
    assert kwargs["plugins"] == []
    assert kwargs["mcp_servers"] == {}
    assert kwargs["env"]["CLAUDE_CONFIG_DIR"]
    assert (Path(kwargs["cwd"]) / ".api-test-skills.yaml").is_file()


def test_persist_restore_transcript_from_payload(tmp_path, monkeypatch, settings):
    monkeypatch.setattr("app.services.workspace._data_dir", settings.data_dir)
    rt = prepare_runtime(settings)
    ws = workspace.workspace_root("s-keep")
    ws.mkdir(parents=True)
    cid = "claude-sess-1"
    cli = rt.cli_transcript_path(ws, cid)
    cli.parent.mkdir(parents=True)
    cli.write_text('{"type":"user"}\n', encoding="utf-8")
    task = rt.spec.claude_home / "tasks" / cid / "1.json"
    task.parent.mkdir(parents=True)
    task.write_text('{"id":"1"}', encoding="utf-8")

    transcript, tasks = rt.dump_cli_session(cid)
    assert transcript == '{"type":"user"}\n'
    assert tasks == {"1.json": '{"id":"1"}'}

    shutil.rmtree(rt.spec.claude_home / "projects")
    shutil.rmtree(rt.spec.claude_home / "tasks")
    shutil.rmtree(ws)
    ws.mkdir(parents=True)
    assert rt.restore_cli_session(ws, cid, transcript, tasks) is True
    assert rt.cli_transcript_path(ws, cid).read_text(encoding="utf-8") == '{"type":"user"}\n'
    assert (rt.spec.claude_home / "tasks" / cid / "1.json").is_file()


def test_resume_omitted_when_transcript_gone(tmp_path, monkeypatch, settings):
    monkeypatch.setattr("app.services.workspace._data_dir", settings.data_dir)
    prepare_runtime(settings)
    row = SessionRow(
        id="s-resume-miss",
        user_name="u",
        git_url="http://g/x.git",
        base_branch="master",
        feature_branch="f",
        claude_session_id="missing-jsonl",
    )
    kwargs = agent.build_agent_options(row, settings)
    assert "resume" not in kwargs


def test_resume_after_restore_from_db_fields(tmp_path, monkeypatch, settings):
    monkeypatch.setattr("app.services.workspace._data_dir", settings.data_dir)
    rt = prepare_runtime(settings)
    row = SessionRow(
        id="s-resume-ok",
        user_name="u",
        git_url="http://g/x.git",
        base_branch="master",
        feature_branch="f",
        claude_session_id="cid-ok",
        claude_transcript="{}\n",
        claude_tasks={"1.json": '{"id":"1"}'},
    )
    kwargs = agent.build_agent_options(row, settings)
    assert kwargs["resume"] == "cid-ok"
    ws = workspace.workspace_root("s-resume-ok")
    assert rt.cli_transcript_path(ws, "cid-ok").is_file()
    assert (rt.spec.claude_home / "tasks" / "cid-ok" / "1.json").is_file()


def test_session_cli_columns_roundtrip(settings):
    db_mod.init_engine(settings.database_url, settings.data_dir)
    sid = "s-db-cli"
    with db_mod.SessionLocal() as s:
        s.add(
            SessionRow(
                id=sid,
                user_name="u",
                git_url="x",
                base_branch="m",
                feature_branch="f",
                claude_session_id="cid",
                claude_transcript='{"a":1}\n',
                claude_tasks={"1.json": "{}"},
            )
        )
        s.commit()
    with db_mod.SessionLocal() as s:
        row = s.get(SessionRow, sid)
        assert row.claude_transcript == '{"a":1}\n'
        assert row.claude_tasks == {"1.json": "{}"}

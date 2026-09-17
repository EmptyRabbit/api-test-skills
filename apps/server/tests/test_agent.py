import asyncio
import sys

import pytest

from app.services import agent


def _mk(cls, **kw):
    return cls(**kw)


def test_translate_assistant_text():
    from claude_agent_sdk import AssistantMessage, TextBlock

    msg = AssistantMessage(content=[TextBlock(text="你好")], model="claude-3-5-sonnet-20241022")
    kind, ev = agent.translate_message(msg)
    assert kind == "agent_message"
    assert ev["role"] == "assistant"
    assert ev["blocks"] == [{"kind": "text", "text": "你好"}]


def test_translate_tool_use_and_result():
    from claude_agent_sdk import ToolResultBlock, ToolUseBlock, UserMessage

    from app.services.agent import translate_blocks

    blocks = translate_blocks([ToolUseBlock(id="t1", name="Bash", input={"command": "ls"})])
    assert blocks == [{"kind": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "ls"}}]

    blocks = translate_blocks(
        [ToolResultBlock(content="file1", tool_use_id="t1", is_error=False)]
    )
    assert blocks == [
        {"kind": "tool_result", "tool_use_id": "t1", "content": "file1", "is_error": False}
    ]


def test_system_prompt_requires_generate_api_tests(tmp_path, monkeypatch):
    from app.db import SessionRow

    monkeypatch.setattr("app.services.workspace._data_dir", tmp_path)
    s = SessionRow(
        id="s-prompt",
        user_name="alice",
        git_url="http://example.invalid/x.git",
        base_branch="master",
        feature_branch="feature/x",
    )
    text = agent.build_system_prompt(s)
    assert "api-generate-api-tests" in text
    assert "禁止跳过" in text
    assert str(tmp_path / "workspaces" / "s-prompt" / "repo") in text
    assert str(tmp_path / "workspaces" / "s-prompt" / "artifacts") in text


def test_new_proactor_returns_loop():
    from app.windows_loop import hidden_popen_kwargs, new_proactor

    loop = new_proactor()
    try:
        assert isinstance(loop, asyncio.AbstractEventLoop)
    finally:
        loop.close()
    flags = hidden_popen_kwargs()
    if sys.platform == "win32":
        assert "creationflags" in flags
    else:
        assert flags == {}


def test_translate_result_message():
    from claude_agent_sdk import ResultMessage

    # SDK 0.2.152 requires: subtype, duration_ms, duration_api_ms, is_error, num_turns, session_id
    msg = ResultMessage(
        subtype="success",
        session_id="cs-1",
        duration_ms=12,
        duration_api_ms=10,
        is_error=False,
        num_turns=1,
        total_cost_usd=0.01,
    )
    kind, ev = agent.translate_message(msg)
    assert kind == "agent_done"
    assert ev["session_id"] == "cs-1"

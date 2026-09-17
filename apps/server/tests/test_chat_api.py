import asyncio

import pytest
from fastapi.testclient import TestClient

from app.db import SessionRow
from app.services import agent as agent_mod


@pytest.fixture
def client(settings, monkeypatch):
    monkeypatch.setattr("app.services.workspace._data_dir", settings.data_dir)
    from app.main import build_app

    return TestClient(build_app(settings))


@pytest.fixture
async def ready_session(settings):
    from app import db as db_mod

    db_mod.init_engine(settings.database_url, settings.data_dir)
    row = SessionRow(
        id="s-agent",
        user_name="alice",
        git_url="http://example.invalid/x.git",
        base_branch="master",
        feature_branch="feature/x",
        status="ready",
    )
    await db_mod.run_db(lambda s: (s.add(row), s.commit()))
    return row.id


class FakeClient:
    """fake ClaudeSDKClient: two messages then done."""

    instances = []

    def __init__(self, options):
        self.options = options
        self.interrupted = False
        FakeClient.instances.append(self)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def query(self, prompt):
        self.prompt = prompt

    async def receive_response(self):
        from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock

        yield AssistantMessage(
            content=[TextBlock(text=f"echo:{self.prompt}")],
            model="claude-3-5-sonnet-20241022",
        )
        yield ResultMessage(
            subtype="success",
            session_id="cs-fake",
            duration_ms=1,
            duration_api_ms=0,
            is_error=False,
            num_turns=1,
            total_cost_usd=0.0,
        )

    async def interrupt(self):
        self.interrupted = True


@pytest.mark.asyncio
async def test_chat_roundtrip_with_fake_client(client, ready_session):
    await agent_mod.run_agent_turn(ready_session, "ping", make_client=FakeClient)

    msgs = client.get(f"/api/sessions/{ready_session}/messages").json()
    roles = [m["role"] for m in msgs]
    assert roles == ["assistant", "result"]
    assert msgs[0]["blocks"][0]["text"] == "echo:ping"

    from app import db as db_mod

    row = await db_mod.run_db(lambda s: s.get(SessionRow, ready_session))
    assert row.claude_session_id == "cs-fake"
    assert row.status == "ready"


def test_chat_endpoint_409_when_running(client, ready_session, monkeypatch):
    # Mark session as running; POST chat should return 409
    monkeypatch.setitem(agent_mod._running, ready_session, object())
    resp = client.post(
        f"/api/sessions/{ready_session}/chat", json={"text": "hi"}
    )
    assert resp.status_code == 409


def test_stop_calls_interrupt(client, ready_session):
    fake = FakeClient(options=None)
    agent_mod._running[ready_session] = fake
    resp = client.post(f"/api/sessions/{ready_session}/stop")
    assert resp.status_code == 200
    assert resp.json() == {"stopped": True}
    assert fake.interrupted is True
    agent_mod._running.pop(ready_session, None)

import asyncio
import logging
import sys

from app import db
from app.config import get_settings
from app.db import MessageRow, SessionRow
from app.services import mcp_oauth, workspace
from app.services.bus import bus
from app.services.claude_runtime import get_runtime
from app.services.snapshots import take_snapshot

logger = logging.getLogger(__name__)


def _selector_loop() -> bool:
    loop = asyncio.get_running_loop()
    return sys.platform == "win32" and isinstance(loop, asyncio.SelectorEventLoop)


async def _on_loop(loop: asyncio.AbstractEventLoop, coro):
    if loop is asyncio.get_running_loop():
        return await coro
    return await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(coro, loop))


def build_system_prompt(s: SessionRow) -> str:
    ws = workspace.workspace_root(s.id)
    return (
        "【本平台任务】\n"
        "本会话用于为当前仓库的代码改动生成接口自动化测试。"
        "只要用户要生成/设计/编写接口测试用例，或分析改动对接口的影响，"
        "必须先用 Skill 工具读取并严格遵循 generate-api-tests（主编排）；"
        "禁止跳过该 skill 自行写 pytest、禁止把 analyze-change-scenarios / "
        "write-pytest-cases 等子 skill 当作入口。"
        "已经处于该流程某阶段时，继续按 generate-api-tests 的阶段门执行，"
        "每阶段产出 md 后暂停等用户确认。\n"
        "【平台环境信息】\n"
        f"- 代码仓库本地路径：{ws / 'repo'}（GitLab: {s.git_url}）\n"
        f"- base 分支：{s.base_branch}，feature 分支：{s.feature_branch}"
        "（当前已 checkout feature）\n"
        f"- 产物目录：{ws / 'artifacts'}\n"
        f"- 当前用户：{s.user_name}\n"
        "使用 generate-api-tests 收集输入时，以上路径/分支/产物目录直接采用，不要再向用户询问。"
    )


def translate_blocks(blocks) -> list[dict]:
    from claude_agent_sdk import TextBlock, ThinkingBlock, ToolResultBlock, ToolUseBlock

    out = []
    for b in blocks:
        if isinstance(b, TextBlock):
            out.append({"kind": "text", "text": b.text})
        elif isinstance(b, ThinkingBlock):
            out.append({"kind": "thinking", "text": b.thinking})
        elif isinstance(b, ToolUseBlock):
            out.append(
                {"kind": "tool_use", "id": b.id, "name": b.name, "input": b.input}
            )
        elif isinstance(b, ToolResultBlock):
            content = b.content
            if not isinstance(content, str):
                content = str(content)
            out.append(
                {
                    "kind": "tool_result",
                    "tool_use_id": b.tool_use_id,
                    "content": content,
                    "is_error": bool(b.is_error),
                }
            )
    return out


def translate_message(msg):
    """Return (event_type, event_dict) or None for messages that are not surfaced."""
    from claude_agent_sdk import AssistantMessage, ResultMessage, SystemMessage, UserMessage

    if isinstance(msg, AssistantMessage):
        blocks = translate_blocks(msg.content)
        return "agent_message", {"type": "agent_message", "role": "assistant", "blocks": blocks}
    if isinstance(msg, UserMessage):
        blocks = translate_blocks(
            msg.content if isinstance(msg.content, list) else []
        )
        if not blocks:
            return None
        return "agent_message", {"type": "agent_message", "role": "user", "blocks": blocks}
    if isinstance(msg, SystemMessage):
        return None
    if isinstance(msg, ResultMessage):
        return "agent_done", {
            "type": "agent_done",
            "duration_ms": msg.duration_ms,
            "cost": msg.total_cost_usd,
            "session_id": msg.session_id,
        }
    return None


def build_agent_options(s: SessionRow, settings) -> dict:
    """ClaudeAgentOptions kwargs: isolated Claude home, no host ~/.claude MCP/skills."""
    runtime = get_runtime()
    ws = workspace.workspace_root(s.id)
    runtime.install_session_files(ws)
    kwargs = dict(
        cwd=str(ws),
        permission_mode=settings.permission_mode,
        system_prompt={
            "type": "preset",
            "preset": "claude_code",
            "append": build_system_prompt(s),
        },
        setting_sources=["user"],
        mcp_servers=mcp_oauth.mcp_servers_for_user(s.user_name),
        strict_mcp_config=True,
        env=runtime.cli_env,
        plugins=[],
    )
    if settings.allowed_tools:
        kwargs["allowed_tools"] = settings.allowed_tools
    cid = s.claude_session_id
    if cid and runtime.restore_cli_session(ws, cid, s.claude_transcript, s.claude_tasks):
        kwargs["resume"] = cid
    elif cid:
        logger.warning(
            "claude transcript missing for resume session=%s claude=%s",
            s.id,
            cid,
        )
    if runtime.spec.model.name:
        kwargs["model"] = runtime.spec.model.name
    return kwargs


async def save_message(session_id: str, role: str, blocks: list[dict]):
    def write(s):
        s.add(MessageRow(session_id=session_id, role=role, content=blocks))
        s.commit()

    return await db.run_db(write)


class _RunningClient:
    """Holds the SDK client; interrupt() is safe from the uvicorn (Selector) loop."""

    def __init__(self):
        self.client = None
        self.loop: asyncio.AbstractEventLoop | None = None

    async def interrupt(self):
        if self.client is None:
            return
        if self.loop is None:
            await self.client.interrupt()
            return
        await _on_loop(self.loop, self.client.interrupt())


_running: dict[str, _RunningClient] = {}


async def _persist_cli_session(session_id: str) -> None:
    def read_id(s2):
        row = s2.get(SessionRow, session_id)
        return row.claude_session_id if row else None

    cid = await db.run_db(read_id)
    if not cid:
        return
    transcript, tasks = await asyncio.to_thread(get_runtime().dump_cli_session, cid)
    if transcript is None and tasks is None:
        return

    def write(s2):
        row = s2.get(SessionRow, session_id)
        if not row:
            return
        if transcript is not None:
            row.claude_transcript = transcript
        if tasks is not None:
            row.claude_tasks = tasks
        s2.commit()

    await db.run_db(write)


async def _drive_turn(
    client,
    session_id: str,
    user_text: str,
    *,
    host_loop: asyncio.AbstractEventLoop,
) -> None:
    async with client:
        await client.query(user_text)
        async for msg in client.receive_response():
            translated = translate_message(msg)
            if translated is None:
                continue
            kind, event = translated

            async def _emit():
                await bus.publish(session_id, event)
                if kind == "agent_done":
                    sid_val = event.get("session_id")
                    if sid_val:

                        def _upd(s2):
                            row = s2.get(SessionRow, session_id)
                            row.claude_session_id = sid_val
                            s2.commit()

                        await db.run_db(_upd)
                    await save_message(session_id, "result", [event])
                else:
                    await save_message(session_id, event["role"], event["blocks"])

            await _on_loop(host_loop, _emit())


async def run_agent_turn(session_id: str, user_text: str, *, make_client=None) -> None:
    real_sdk = make_client is None
    if make_client is None:
        from claude_agent_sdk import ClaudeSDKClient

        make_client = ClaudeSDKClient

    settings = get_settings()
    s = await db.run_db(lambda sess: sess.get(SessionRow, session_id))
    from claude_agent_sdk import ClaudeAgentOptions

    options = ClaudeAgentOptions(
        **await asyncio.to_thread(build_agent_options, s, settings)
    )
    host_loop = asyncio.get_running_loop()
    slot = _RunningClient()
    _running[session_id] = slot

    async def _once() -> None:
        client = make_client(options=options)
        slot.client = client
        slot.loop = asyncio.get_running_loop()
        await _drive_turn(client, session_id, user_text, host_loop=host_loop)

    try:
        if real_sdk and _selector_loop():
            def _thread() -> None:
                loop = asyncio.ProactorEventLoop()
                try:
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(_once())
                finally:
                    loop.close()
                    asyncio.set_event_loop(None)

            await asyncio.to_thread(_thread)
        else:
            await _once()
    except Exception as e:  # noqa: BLE001
        logger.exception("agent turn failed")
        await bus.publish(session_id, {"type": "agent_error", "message": str(e)})
    finally:
        _running.pop(session_id, None)

        def _ready(s2):
            row = s2.get(SessionRow, session_id)
            row.status = "ready"
            s2.commit()

        await db.run_db(_ready)
        try:
            await _persist_cli_session(session_id)
        except Exception:  # noqa: BLE001
            logger.exception("persist claude transcript failed")
        try:
            await take_snapshot(session_id, "agent_done")
        except Exception:  # noqa: BLE001
            logger.exception("snapshot after agent turn failed")


async def stop_agent(session_id: str) -> bool:
    client = _running.get(session_id)
    if client is None:
        return False
    await client.interrupt()
    return True

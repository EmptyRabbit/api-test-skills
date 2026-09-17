"""Windows event loop that can spawn subprocesses (git / claude / code-server).

uvicorn --reload sets use_subprocess=True, and uvicorn.loops.asyncio then
returns SelectorEventLoop on Windows. That loop raises NotImplementedError
from asyncio.create_subprocess_exec / anyio.open_process.

Pass:  --loop app.windows_loop:new_proactor
"""

from __future__ import annotations

import asyncio
import subprocess
import sys


def new_proactor() -> asyncio.AbstractEventLoop:
    if sys.platform == "win32":
        return asyncio.ProactorEventLoop()
    return asyncio.new_event_loop()


def hidden_popen_kwargs() -> dict:
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}

"""Dev entry: keep a Windows Proactor loop even when --reload is on."""

from __future__ import annotations

import sys

import uvicorn


def uvicorn_dev_kwargs() -> dict:
    """只盯 app/。data/ 里 code-server 与 pytest 会写文件，热重载会掐掉 VS Code WebSocket。"""
    kwargs: dict = {
        "app": "app.main:create_app",
        "factory": True,
        "host": "127.0.0.1",
        "port": 8000,
        "reload": True,
        "reload_dirs": ["app"],
    }
    if sys.platform == "win32":
        kwargs["loop"] = "app.windows_loop:new_proactor"
    return kwargs


def main() -> None:
    uvicorn.run(**uvicorn_dev_kwargs())


if __name__ == "__main__":
    main()

from fastapi import FastAPI

from app.config import Settings, get_settings


def build_app(settings: Settings) -> FastAPI:
    from app import db
    from app.services.claude_runtime import prepare_runtime

    db.init_engine(settings.database_url, settings.data_dir)
    prepare_runtime(settings)
    app = FastAPI(title="api-test-platform")

    @app.get("/api/health")
    def health():
        from sqlalchemy import text

        with db.SessionLocal() as s:
            s.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}

    from app.routers import sessions

    app.include_router(sessions.router)

    from app.routers import events

    app.include_router(events.router)

    from app.routers import chat, mcp_oauth as mcp_oauth_router

    app.include_router(chat.router)
    app.include_router(mcp_oauth_router.router)

    from app.routers import files

    app.include_router(files.router)

    from app.routers import vscode
    from app.services import vscode as vscode_service

    app.include_router(vscode.router)

    @app.on_event("startup")
    async def _start_sweeper():
        import asyncio

        async def loop():
            while True:
                await asyncio.sleep(60)
                await vscode_service.manager.sweep()

        asyncio.get_running_loop().create_task(loop())

    from pathlib import Path

    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    dist = (Path(__file__).resolve().parent.parent.parent / "web" / "dist").resolve()
    if dist.is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa(full_path: str):
            if full_path == "api" or full_path.startswith("api/"):
                from fastapi import HTTPException

                raise HTTPException(status_code=404, detail="not found")
            target = (dist / full_path).resolve()
            if full_path and target.is_file() and target.is_relative_to(dist):
                return FileResponse(target)
            return FileResponse(dist / "index.html")

    return app


def create_app() -> FastAPI:
    return build_app(get_settings())

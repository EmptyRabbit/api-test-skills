import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Engine,
    ForeignKey,
    String,
    Text,
    create_engine,
    inspect,
    text,
)
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SessionRow(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_name: Mapped[str] = mapped_column(String(100))
    git_url: Mapped[str] = mapped_column(Text)
    base_branch: Mapped[str] = mapped_column(String(200))
    feature_branch: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(20), default="cloning")
    claude_session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    claude_transcript: Mapped[str | None] = mapped_column(
        Text().with_variant(LONGTEXT, "mysql"), nullable=True
    )
    claude_tasks: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str] = mapped_column(Text, default="")
    model_name: Mapped[str] = mapped_column(String(200), default="")
    auth_token: Mapped[str] = mapped_column(Text, default="")
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class MessageRow(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class SnapshotRow(Base):
    __tablename__ = "snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    trigger: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class McpOAuthTokenRow(Base):
    __tablename__ = "mcp_oauth_tokens"

    user_name: Mapped[str] = mapped_column(String(100), primary_key=True)
    server_name: Mapped[str] = mapped_column(String(200), primary_key=True)
    access_token: Mapped[str] = mapped_column(Text, default="")
    refresh_token: Mapped[str] = mapped_column(Text, default="")
    cas_account: Mapped[str] = mapped_column(String(200), default="")
    resource: Mapped[str] = mapped_column(Text, default="")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class McpOAuthClientRow(Base):
    __tablename__ = "mcp_oauth_clients"

    issuer: Mapped[str] = mapped_column(String(500), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(200))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class SnapshotFileRow(Base):
    __tablename__ = "snapshot_files"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("snapshots.id"), index=True)
    path: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)


_engine: Engine | None = None
SessionLocal: sessionmaker | None = None


def init_engine(database_url: str, data_dir) -> Engine:
    global _engine, SessionLocal
    if not database_url:
        data_dir.mkdir(parents=True, exist_ok=True)
        database_url = f"sqlite:///{data_dir / 'platform.db'}"
    _engine = create_engine(database_url)
    SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    Base.metadata.create_all(_engine)
    _ensure_session_cli_columns(_engine)
    return _engine


def _ensure_session_cli_columns(engine: Engine) -> None:
    cols = {c["name"] for c in inspect(engine).get_columns("sessions")}
    mysql = engine.dialect.name == "mysql"
    wanted = {
        "claude_transcript": "LONGTEXT" if mysql else "TEXT",
        "claude_tasks": "JSON" if mysql else "TEXT",
        "model_name": "VARCHAR(200)",
        "auth_token": "LONGTEXT" if mysql else "TEXT",
    }
    missing = [(name, sqltype) for name, sqltype in wanted.items() if name not in cols]
    if not missing:
        return
    with engine.begin() as conn:
        for name, sqltype in missing:
            conn.execute(text(f"ALTER TABLE sessions ADD COLUMN {name} {sqltype}"))


def run_db(fn):
    """在异步上下文中线程池执行同步 DB 会话块：fn(session) -> result。"""

    def _wrapper():
        with SessionLocal() as s:
            return fn(s)

    return asyncio.to_thread(_wrapper)


def new_session_id() -> str:
    return str(uuid.uuid4())

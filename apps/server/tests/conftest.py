import pytest
from app.config import Settings


@pytest.fixture
def settings(tmp_path):
    return Settings(data_dir=tmp_path / "data", database_url="")


@pytest.fixture(autouse=True)
def _no_host_platform_yaml(monkeypatch):
    monkeypatch.delenv("PLATFORM_CONFIG", raising=False)
    monkeypatch.setattr("app.platform_config.resolve_config_path", lambda: None)


@pytest.fixture(autouse=True)
def _reset_db_globals():
    yield
    from app import db
    from app.services.claude_runtime import reset_runtime

    db._engine = None
    db.SessionLocal = None
    reset_runtime()

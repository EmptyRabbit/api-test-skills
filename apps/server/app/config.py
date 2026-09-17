from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    data_dir: Path = Path("data")
    # 留空则自动落到 <data_dir>/platform.db；切 MySQL 填 mysql+pymysql://...
    database_url: str = ""
    # bypassPermissions（默认，自动放行）或 default + allowed_tools 白名单
    permission_mode: str = "bypassPermissions"
    allowed_tools: list[str] = []
    code_server_bin: str = "code-server"
    code_server_idle_minutes: int = 30

    model_config = {"env_prefix": "PLATFORM_"}


@lru_cache
def get_settings() -> Settings:
    return Settings()

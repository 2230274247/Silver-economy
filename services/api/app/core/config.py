from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DATABASE_NAMES = {"silver_memory_demo_v01", "silver_memory_demo_v01_test"}


def validated_database_url(value: str, *, test_only: bool = False) -> URL:
    """Never allow development/migration scripts to connect to unrelated schemas."""
    try:
        url = make_url(value)
        valid = (
            url.drivername == "mysql+pymysql"
            and url.host in {"127.0.0.1", "localhost"}
            and url.port == 13306
            and url.username == "silver_demo"
            and bool(url.password)
            and url.database in DATABASE_NAMES
            and (not test_only or url.database == "silver_memory_demo_v01_test")
        )
    except (ArgumentError, ValueError, TypeError):
        valid = False
    if not valid:
        raise ValueError("Database must be an isolated Silver-economy schema on port 13306")
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")

    database_url: SecretStr = SecretStr("")
    test_database_url: SecretStr = SecretStr("")


@lru_cache
def get_settings() -> Settings:
    return Settings()

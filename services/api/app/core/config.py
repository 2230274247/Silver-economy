from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, SecretStr, field_validator
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
    model_config = SettingsConfigDict(
        env_file=(
            PROJECT_ROOT / ".env",
            PROJECT_ROOT / ".env.deepseek",
            PROJECT_ROOT / ".env.amap",
            PROJECT_ROOT / ".env.notifications",
        ),
        extra="ignore",
    )

    database_url: SecretStr = SecretStr("")
    test_database_url: SecretStr = SecretStr("")
    session_ttl_seconds: int = 43200
    cookie_secure: bool = False
    ui_test_mode: bool = False
    llm_provider: Literal["mock", "deepseek"] = "mock"
    deepseek_api_key: SecretStr = SecretStr("")
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-flash"
    deepseek_max_output_tokens: int = Field(256, ge=16, le=1024)
    deepseek_task_max_output_tokens: int = Field(512, ge=256, le=1024)
    deepseek_daily_request_limit: int = Field(10, ge=0, le=100)
    deepseek_daily_token_limit: int = Field(20000, ge=0, le=200000)
    deepseek_search_enabled: bool = True
    admin_daily_request_limit: int = Field(100, ge=0, le=10000)
    admin_daily_token_limit: int = Field(200000, ge=0, le=10000000)
    admin_max_output_tokens: int = Field(1024, ge=256, le=8192)
    maps_provider: Literal["disabled", "mock", "amap"] = "disabled"
    amap_web_service_key: SecretStr = SecretStr("")
    amap_daily_request_limit: int = Field(20, ge=0, le=1000)
    notifications_provider: Literal["mock", "disabled", "unipush_bridge"] = "mock"
    notification_device_encryption_key: SecretStr = SecretStr("")
    uni_push_bridge_url: str = ""
    uni_push_bridge_token: SecretStr = SecretStr("")
    worker_lease_seconds: int = Field(60, ge=15, le=600)
    worker_delivery_grace_minutes: int = Field(15, ge=1, le=1440)

    @field_validator("deepseek_base_url")
    @classmethod
    def official_endpoint(cls, value):
        if value.rstrip("/") not in {"https://api.deepseek.com", "https://api.deepseek.com/v1"}:
            raise ValueError("Only the official DeepSeek HTTPS endpoint is allowed")
        return value.rstrip("/")

    @field_validator("uni_push_bridge_url")
    @classmethod
    def https_bridge_only(cls, value):
        if not value:
            return ""
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("Uni-push bridge must use an HTTPS URL without embedded credentials")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()

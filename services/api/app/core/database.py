from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings, validated_database_url


def build_engine(value: str, *, test_only: bool = False):
    return create_engine(
        validated_database_url(value, test_only=test_only),
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={"connect_timeout": 3, "read_timeout": 5, "write_timeout": 5},
    )


@lru_cache
def get_engine():
    return build_engine(get_settings().database_url.get_secret_value())


def get_session():
    with Session(get_engine(), expire_on_commit=False) as session:
        yield session


def session_factory():
    return sessionmaker(get_engine(), expire_on_commit=False)

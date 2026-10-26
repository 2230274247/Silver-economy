import os

import pytest
from alembic.config import Config
from sqlalchemy.orm import Session

from alembic import command
from app.core.config import PROJECT_ROOT, get_settings, validated_database_url
from app.core.database import build_engine


def migration_config(url: str) -> Config:
    config = Config(str(PROJECT_ROOT / "services/api/alembic.ini"))
    config.attributes.update(database_url=url, test_only=True)
    return config


@pytest.fixture(scope="session")
def mysql_engine():
    value = get_settings().test_database_url.get_secret_value()
    if not value:
        if os.getenv("REQUIRE_MYSQL_TESTS") == "1":
            pytest.fail("Independent MySQL test configuration is required")
        pytest.skip("Independent MySQL not configured; run scripts/init-dev-db.py")
    validated_database_url(value, test_only=True)
    command.upgrade(migration_config(value), "head")
    engine = build_engine(value, test_only=True)
    yield engine
    engine.dispose()


@pytest.fixture
def db(mysql_engine):
    with mysql_engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session
        transaction.rollback()

import uuid

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from app.core.config import get_settings, validated_database_url
from app.models.entities import Conversation, Message, User
from tests.conftest import migration_config


@pytest.mark.mysql
def test_empty_schema_upgrade_repeat_downgrade_upgrade(mysql_engine):
    config = migration_config(get_settings().test_database_url.get_secret_value())
    command.downgrade(config, "base")
    assert set(inspect(mysql_engine).get_table_names()) == {"alembic_version"}
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    command.check(config)
    tables = set(inspect(mysql_engine).get_table_names())
    assert tables == {
        "alembic_version",
        "users",
        "auth_sessions",
        "conversations",
        "messages",
        "memory_facts",
        "memory_sources",
        "memory_uses",
        "memory_revisions",
        "life_events",
        "reminders",
        "task_drafts",
        "model_usage",
        "model_budget",
        "map_requests",
        "map_budget",
    }
    with mysql_engine.connect() as connection:
        assert connection.execute(text("SELECT @@session.time_zone")).scalar_one() == "+00:00"


@pytest.mark.mysql
def test_database_foreign_key_rejects_cross_user_message(db):
    a = User(login_name=f"synthetic-a-{uuid.uuid4()}", password_hash="not-a-login-hash")
    b = User(login_name=f"synthetic-b-{uuid.uuid4()}", password_hash="not-a-login-hash")
    db.add_all([a, b])
    db.flush()
    conversation = Conversation(user_id=a.id)
    db.add(conversation)
    db.flush()
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(
            Message(user_id=b.id, conversation_id=conversation.id, role="user", content="合成测试")
        )
        db.flush()


@pytest.mark.parametrize("schema", ["ALE_AI_MySQL", "mysql", "other_project"])
def test_unrelated_database_is_rejected_without_connection(schema):
    with pytest.raises(ValueError, match="isolated Silver-economy"):
        validated_database_url(f"mysql+pymysql://silver_demo:synthetic@127.0.0.1:13306/{schema}")


def test_test_migration_cannot_target_development_schema():
    with pytest.raises(ValueError):
        validated_database_url(
            "mysql+pymysql://silver_demo:synthetic@127.0.0.1:13306/silver_memory_demo_v01",
            test_only=True,
        )

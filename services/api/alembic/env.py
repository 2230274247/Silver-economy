from alembic import context
from app.core.config import get_settings
from app.core.database import build_engine
from app.models import entities  # noqa: F401
from app.models.base import Base

config = context.config
value = config.attributes.get("database_url") or get_settings().database_url.get_secret_value()
engine = build_engine(value, test_only=bool(config.attributes.get("test_only")))
with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()
engine.dispose()

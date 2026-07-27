from logging.config import fileConfig
import os
from sqlalchemy import engine_from_config, pool
from alembic import context

# Import models to register them with Base.metadata
from app.database import Base
from app.config import settings
import app.models

target_metadata = Base.metadata

# Get alembic config
config = context.config

# Configure logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Resolve the database URL the same way the app does so `alembic` and the
# running service always target the same database. Precedence:
#   1. an explicit DATABASE_URL in the shell environment (CI / one-off overrides)
#   2. app settings, which load the project-root .env (the app's real DB)
#   3. the alembic.ini placeholder (last resort)
url = os.getenv("DATABASE_URL") or settings.DATABASE_URL or config.get_main_option("sqlalchemy.url")
config.set_main_option("sqlalchemy.url", url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

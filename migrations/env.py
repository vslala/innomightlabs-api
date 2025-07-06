import os
from logging.config import fileConfig

from sqlalchemy import create_engine, pool
from alembic import context

from app.common.db_connect import make_base_url, make_connect_args

# —— Config and Logging ————————————————————————————————————————————————
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Environment
POSTGRES_USER = os.environ.get("POSTGRES_USER")
POSTGRES_DB = os.environ.get("POSTGRES_DB")

if not POSTGRES_USER or not POSTGRES_DB:
    raise RuntimeError("POSTGRES_USER and POSTGRES_DB must be set")

# MetaData for autogenerate (if you have)
target_metadata = None


def run_migrations_offline():
    url = make_base_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    # Build engine with dynamic credentials
    engine = create_engine(
        make_base_url(),
        connect_args=make_connect_args(),
        poolclass=pool.NullPool,
    )

    with engine.connect() as connection:
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

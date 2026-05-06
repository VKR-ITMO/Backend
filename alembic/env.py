from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from alembic import context
from vkr_itmo.config import AppConfig
from vkr_itmo.db.models import *

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
load_dotenv()
alembic_config = context.config
section = alembic_config.config_ini_section
app_config = AppConfig()
alembic_config.set_section_option(section, "POSTGRES_DB", app_config.POSTGRES_DB)
alembic_config.set_section_option(section, "POSTGRES_HOST", app_config.POSTGRES_HOST)
alembic_config.set_section_option(section, "POSTGRES_USER", app_config.POSTGRES_USER)
alembic_config.set_section_option(
    section, "POSTGRES_PASSWORD", app_config.POSTGRES_PASSWORD.get_secret_value()
)
alembic_config.set_section_option(section, "POSTGRES_PORT", str(app_config.POSTGRES_PORT))

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if alembic_config.config_file_name is not None:
    fileConfig(alembic_config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
fileConfig(alembic_config.config_file_name, disable_existing_loggers=False)

target_metadata = DeclarativeBase.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = alembic_config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        alembic_config.get_section(alembic_config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
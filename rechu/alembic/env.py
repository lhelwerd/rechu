"""
This is a Python script that is run whenever the alembic migration tool is
invoked. It contains instructions to configure and generate a SQLAlchemy
engine, procure a connection from that engine along with a transaction, and
then invoke the migration engine, using the connection as a source of
database connectivity.
"""

from logging.config import fileConfig

from alembic import context

from rechu.database import Database
from rechu.models import Base
from rechu.settings import Settings

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# TARGET_METADATA = mymodel.Base.metadata
TARGET_METADATA = Base.metadata

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
    settings = Settings.get_settings()
    url = settings.get("database", "uri")
    context.configure(
        url=url,
        target_metadata=TARGET_METADATA,
        render_as_batch=True,
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

    database = Database()
    connectable = database.engine
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=TARGET_METADATA,
            render_as_batch=True
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

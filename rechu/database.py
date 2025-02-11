"""
Database access.
"""

from pathlib import Path
import sys
from types import TracebackType
from typing import Optional, TextIO
from alembic.config import Config
from alembic import script
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.pool import ConnectionPoolEntry
from sqlalchemy.orm import Session
from .models.base import Base
from .settings import Settings

class Database:
    """
    Database provider.
    """

    def __init__(self) -> None:
        settings = Settings.get_settings()
        self.engine = create_engine(settings.get('database', 'uri'))
        self.session: Optional[Session] = None

        if self.engine.name == 'sqlite':
            event.listen(Engine, "connect", self._set_sqlite_pragma)

    @staticmethod
    def _set_sqlite_pragma(connection: DBAPIConnection,
                           _connection_record: ConnectionPoolEntry) -> None:
        settings = Settings.get_settings()
        pragma_value = "OFF" \
            if settings.get('database', 'foreign_keys').lower() == 'off' \
            else "ON"
        cursor = connection.cursor()
        cursor.execute(f"PRAGMA foreign_keys = {pragma_value}")
        cursor.close()

    def create_schema(self) -> None:
        """
        Perform schema creation on an empty database, marking it as up to date
        using alembic's stamp command.
        """

        with self as session:
            Base.metadata.create_all(session.get_bind())

        alembic_config = self.get_alembic_config()
        directory = script.ScriptDirectory.from_config(alembic_config)
        with self.engine.begin() as connection:
            migration_context = MigrationContext.configure(connection)
            migration_context.stamp(directory, "head")

    def drop_schema(self) -> None:
        """
        Clean up the database by removing all model tables.
        """

        with self as session:
            Base.metadata.drop_all(session.get_bind())

    @staticmethod
    def get_alembic_config(stdout: TextIO = sys.stdout) -> Config:
        """
        Retrieve the configuration object for alembic preconfigured for rechu.
        """

        package_root = Path(__file__).resolve().parent
        return Config(package_root / 'alembic.ini', stdout=stdout)

    def __del__(self) -> None:
        self.close()

    def __enter__(self) -> Session:
        if self.session is not None:
            raise RuntimeError('Detected nested database session attempts')
        self.session = Session(self.engine)
        return self.session

    def __exit__(self, exc_type: Optional[type[BaseException]],
                 exc_value: Optional[BaseException],
                 traceback: Optional[TracebackType]) -> None:
        if self.session is not None:
            self.session.commit()
        self.close()

    def close(self) -> None:
        """
        Close any open database session connection.
        """

        if self.session is not None:
            self.session.close()
            self.session = None

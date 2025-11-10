"""
Database access.
"""

import sys
from pathlib import Path
from types import TracebackType
from typing import TextIO

from alembic import script
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.orm import Session
from sqlalchemy.pool import ConnectionPoolEntry

from .models import Base
from .settings import Settings


class Database:
    """
    Database provider.
    """

    def __init__(self) -> None:
        settings = Settings.get_settings()
        self.engine: Engine = create_engine(settings.get("database", "uri"))
        self.session: Session | None = None

        if self.engine.name == "sqlite":
            event.listen(Engine, "connect", self._set_sqlite_pragma)

    @staticmethod
    def _set_sqlite_pragma(
        connection: DBAPIConnection, _connection_record: ConnectionPoolEntry
    ) -> None:
        settings = Settings.get_settings()
        pragma_value = (
            "OFF"
            if settings.get("database", "foreign_keys").lower() == "off"
            else "ON"
        )
        cursor = connection.cursor()
        cursor.execute(f"PRAGMA foreign_keys = {pragma_value}")
        cursor.close()

    def create_schema(self) -> None:
        """
        Perform schema creation on an empty database, marking it as up to date
        using alembic's stamp command.
        """

        Base.metadata.create_all(self.engine)

        alembic_config = self.get_alembic_config()
        directory = script.ScriptDirectory.from_config(alembic_config)
        with self.engine.begin() as connection:
            migration_context = MigrationContext.configure(connection)
            migration_context.stamp(directory, "head")

    def drop_schema(self) -> None:
        """
        Clean up the database by removing all model tables.
        """

        Base.metadata.drop_all(self.engine)

    @staticmethod
    def get_alembic_config(stdout: TextIO = sys.stdout) -> Config:
        """
        Retrieve the configuration object for alembic preconfigured for rechu.
        """

        package_root = Path(__file__).resolve().parent
        return Config(package_root / "alembic.ini", stdout=stdout)

    def __del__(self) -> None:
        self.close()

    def __enter__(self) -> Session:
        if self.session is not None:
            raise RuntimeError("Detected nested database session attempts")
        self.session = Session(self.engine)
        return self.session

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
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

    def clear(self) -> None:
        """
        Reset any permanent settings-based state of the database.
        """

        if event.contains(Engine, "connect", self._set_sqlite_pragma):
            event.remove(Engine, "connect", self._set_sqlite_pragma)

"""
Database access.
"""

from pathlib import Path
import sys
from types import TracebackType
from typing import Optional, TextIO, Union
from alembic.config import Config
from alembic import command, context
from sqlalchemy import create_engine, Table
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

    def create_schema(self) -> None:
        """
        Perform schema creation on an empty database, marking it as up to date
        using alembic's stamp command.
        """

        with self as session:
            Base.metadata.create_all(session.get_bind())

        command.stamp(self.get_alembic_config(), "head")

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

    @staticmethod
    def offline_table(model: Union[type[Base], Table]) -> Optional[Table]:
        """
        Retrieve an SQLAlchemy Table reference object when running an alembic
        migration in offline (SQL generation) mode. Under SQLite, we often need
        to perform a "move and copy" migration; in online mode, SQLAlchemy can
        perform reflection to deduce what to do, but when using offline mode,
        the entire table needs to be provided from the model. To avoid overhead
        in online migrations, we skip providing the table from model, so only
        during offline migrations will we provide the table.
        """

        if not context.is_offline_mode():
            return None
        if isinstance(model, Table):
            return model
        if hasattr(model, '__table__') and isinstance(model.__table__, Table):
            return model.__table__
        return None

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

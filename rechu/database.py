"""
Database access.
"""

from types import TracebackType
from typing import Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from .settings import Settings

class Database:
    """
    Database provider.
    """

    def __init__(self) -> None:
        settings = Settings.get_settings()
        self.engine = create_engine(settings.get('database', 'uri'))
        self.session: Optional[Session] = None

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

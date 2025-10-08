"""
Database schema creation subcommand.
"""

from typing import final
from typing_extensions import override
from .base import Base
from ..database import Database

@final
@Base.register("create")
class Create(Base):
    """
    Create the database with the database schema.
    """

    subparser_keywords = {
        'help': 'Create the database and schema',
        'description': 'Create database schema tables at the configured URI.'
    }

    @override
    def run(self) -> None:
        database = Database()
        database.create_schema()

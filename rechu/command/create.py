"""
Database schema creation subcommand.
"""

from dataclasses import dataclass
from typing import ClassVar

from typing_extensions import override

from ..database import Database
from .base import Base, SubparserKeywords


@dataclass
@Base.register("create")
class Create(Base):
    """
    Create the database with the database schema.
    """

    subparser_keywords: ClassVar[SubparserKeywords] = {
        "help": "Create the database and schema",
        "description": "Create database schema tables at the configured URI.",
    }

    @override
    def run(self) -> None:
        database = Database()
        database.create_schema()

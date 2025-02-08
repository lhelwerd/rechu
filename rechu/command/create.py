"""
Database schema creation subcommand.
"""

from .base import Base
from ..database import Database

@Base.register("create")
class Create(Base):
    """
    Create the database with the database schema.
    """

    def run(self) -> None:
        database = Database()
        database.create_schema()

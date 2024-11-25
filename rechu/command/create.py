"""
Database schema creation subcommand.
"""

from .base import Base
from ..database import Database
from ..models.base import Base as ModelBase

@Base.register("create")
class Create(Base):
    """
    Create the database with the database schema.
    """

    def run(self) -> None:
        with Database() as session:
            ModelBase.metadata.create_all(session.get_bind())

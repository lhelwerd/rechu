"""
Subcommand to run Alembic commands for database migration.
"""

import sys
from alembic import config
from .base import Base
from ..database import Database

@Base.register("alembic")
class Alembic(Base):
    """
    Run an alembic command.
    """

    def run(self) -> None:
        alembic_config = Database.get_alembic_config()

        subcommand = sys.argv[2] if len(sys.argv) > 2 else ""
        args = ["-c", str(alembic_config.config_file_name), subcommand]
        if subcommand == "revision":
            args.append("--autogenerate")
        args.extend(sys.argv[3:])

        config.main(argv=args, prog="rechu alembic")

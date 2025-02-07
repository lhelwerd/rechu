"""
Subcommand to run Alembic commands for database migration.
"""

from pathlib import Path
import sys
from alembic import config
from .base import Base

@Base.register("alembic")
class Alembic(Base):
    """
    Run an alembic command.
    """

    def run(self) -> None:
        package_root = Path(__file__).resolve().parents[1]
        alembic_config = package_root / 'alembic.ini'

        subcommand = sys.argv[2] if len(sys.argv) > 2 else ""
        args = sys.argv[3:]
        if subcommand == "revision":
            args.append("--autogenerate")

        config.main(argv=["-c", str(alembic_config), subcommand] + args)

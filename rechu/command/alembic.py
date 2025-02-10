"""
Subcommand to run Alembic commands for database migration.
"""

from alembic import config
from .base import Base
from ..database import Database

@Base.register("alembic")
class Alembic(Base):
    """
    Run an alembic command.
    """

    subparser_keywords = {
        # Let alembic handle `rechu alembic --help` argument
        'add_help': False,
        # Describe command in `rechu --help`
        'help': 'Perform database revision management',
        # Pass along all arguments to alembic even if they start with dashes
        'prefix_chars': '\x00'
    }
    subparser_arguments = [
        ('args', {'nargs': '*', 'help': 'alembic arguments'})
    ]

    def __init__(self) -> None:
        super().__init__()
        self.args: list[str] = []

    def run(self) -> None:
        alembic_config = Database.get_alembic_config()

        subcommand = self.args[0] if self.args else ""
        args = ["-c", str(alembic_config.config_file_name)]
        if subcommand != "":
            args.append(subcommand)
        if subcommand == "revision":
            args.append("--autogenerate")
        args.extend(self.args[1:])

        config.main(argv=args, prog=f"{self.program} {self.subcommand}")

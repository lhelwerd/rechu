"""
Subcommand to run Alembic commands for database migration.
"""

from typing import ClassVar, final
from typing_extensions import override
from alembic.config import CommandLine
from .base import Base, SubparserArguments, SubparserKeywords
from ..database import Database


@final
@Base.register("alembic")
class Alembic(Base):
    """
    Run an alembic command.
    """

    subparser_keywords: ClassVar[SubparserKeywords] = {
        # Let alembic handle `rechu alembic --help` argument
        "add_help": False,
        # Describe command in `rechu --help`
        "help": "Perform database revision management",
        # Pass along all arguments to alembic even if they start with dashes
        "prefix_chars": "\x00",
    }
    subparser_arguments: ClassVar[SubparserArguments] = [
        ("args", {"nargs": "*", "help": "alembic arguments"})
    ]

    def __init__(self) -> None:
        super().__init__()
        self.args: list[str] = []

    @override
    def run(self) -> None:
        alembic_config = Database.get_alembic_config()

        alembic_cmd = CommandLine(prog=f"{self.program} {self.subcommand}")

        subcommand = self.args[0] if self.args else ""
        args: list[str] = []
        if subcommand != "":
            args.append(subcommand)
        if subcommand == "revision":
            args.append("--autogenerate")
        args.extend(self.args[1:])

        alembic_options = alembic_cmd.parser.parse_args(args)
        alembic_cmd.run_cmd(alembic_config, alembic_options)

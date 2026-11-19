"""
Base for receipt subcommands.
"""

import logging
import os
from abc import ABCMeta, abstractmethod
from argparse import ArgumentParser, Namespace
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, TypeVar

from typing_extensions import TypedDict

from .. import __name__ as NAME, __version__ as VERSION
from ..settings import Settings


class SubparserKeywords(TypedDict, total=False):
    """
    Keyword arguments acceptable for subcommands to register to a subparser of
    an argument parser.
    """

    help: str | None
    aliases: Sequence[str]
    description: str | None
    epilog: str | None
    prefix_chars: str
    fromfile_prefix_chars: str | None
    add_help: bool
    allow_abbrev: bool


class ArgumentKeywords(TypedDict, total=False):
    """
    Keyword arguments acceptable for registering an argument to a subparser of
    an argument parser.
    """

    action: str
    nargs: int | str | None
    const: Any
    default: Any
    type: Callable[[str], Any]
    choices: Iterable[Any] | None
    required: bool
    help: str | None
    metavar: str | tuple[str, ...] | None
    dest: str | None


ArgumentSpec = tuple[str | tuple[str, ...], ArgumentKeywords]
SubparserArguments = Iterable[ArgumentSpec]


@dataclass
class _SubcommandHolder(Namespace):
    subcommand: str = ""
    log: str = "INFO"

    def __post_init__(self) -> None:
        super().__init__()


CommandT = TypeVar("CommandT", bound="Base")

LOGGER = logging.getLogger(__name__)


@dataclass
class Base(Namespace, metaclass=ABCMeta):
    """
    Abstract command handling.
    """

    # Class member variable for registering programs
    _commands: ClassVar[dict[str, type["Base"]]] = {}

    name: ClassVar[str] = ""

    # Registration of executed program and subcommand name
    program: str = NAME
    subcommand: str = ""

    # Member varialbes that commands can override to register itself, its
    # keyword metadata and its arguments
    subparser_keywords: ClassVar[SubparserKeywords] = {}
    subparser_arguments: ClassVar[SubparserArguments] = []

    # Member variables set up by the base command
    settings: Settings = field(
        default_factory=Settings.get_settings, init=False
    )
    logger: logging.Logger = field(default=LOGGER, init=False)

    @classmethod
    def register(cls, name: str) -> Callable[[type[CommandT]], type[CommandT]]:
        """
        Register a subcommand.
        """

        def decorator(subclass: type[CommandT]) -> type[CommandT]:
            cls._commands[name] = subclass
            subclass.name = name
            return subclass

        return decorator

    @classmethod
    def get_command(cls, name: str) -> "Base":
        """
        Create a command instance for the given subcommand name.
        """

        return cls._commands[name](program=cls.program, subcommand=name)

    @classmethod
    def register_arguments(cls) -> ArgumentParser:
        """
        Create an argument parser for all registered subcommands.
        """

        parser = ArgumentParser(
            prog=cls.program, description="Receipt cataloging hub"
        )
        _ = parser.add_argument(
            "--version", action="version", version=f"{NAME} {VERSION}"
        )
        _ = parser.add_argument(
            "--log",
            choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
            default="INFO",
            help="Log level",
        )
        subparsers = parser.add_subparsers(
            dest="subcommand", help="Subcommands"
        )
        for name, subclass in cls._commands.items():
            subparser = subparsers.add_parser(
                name, **subclass.subparser_keywords
            )
            for argument, keywords in subclass.subparser_arguments:
                if isinstance(argument, str):
                    _ = subparser.add_argument(argument, **keywords)
                else:
                    _ = subparser.add_argument(*argument, **keywords)

        return parser

    @classmethod
    def start(cls, executable: str, argv: Sequence[str]) -> int:
        """
        Parse arguments from a sequence of command line arguments and determine
        which command to run, register any arguments to it and finally execute
        the action of the command. Returns an exit status code.
        """

        cls.program = Path(argv[0]).name
        if cls.program == "__main__.py":
            python = Path(executable)
            if str(python.parent) in os.get_exec_path():
                executable = python.name
            cls.program = f"{executable} -m {NAME}"

        parser = cls.register_arguments()
        if len(argv) <= 1:
            parser.print_usage()
            return 1

        holder = _SubcommandHolder()
        _ = parser.parse_known_args(argv[1:], namespace=holder)

        logging.getLogger(NAME).setLevel(getattr(logging, holder.log, 0))

        command = cls.get_command(holder.subcommand)
        _ = parser.parse_args(argv[1:], namespace=command)
        return command.run() or 0

    def __post_init__(self) -> None:
        super().__init__()
        if self.subcommand == "":
            self.subcommand = self.name
        self.settings = Settings.get_settings()
        self.logger = logging.getLogger(self.__class__.__module__)

    @abstractmethod
    def run(self) -> int | None:
        """
        Execute the command and return a status code.
        """

        raise NotImplementedError("Must be implemented by subclasses")

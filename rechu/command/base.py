"""
Base for receipt subcommands.
"""

from argparse import ArgumentParser, FileType, Namespace
import logging
import os
from pathlib import Path
from typing import Callable, Iterable, Generic, Optional, Sequence, TypeVar, \
    Union
from typing_extensions import TypedDict
from .. import __name__ as NAME, __version__ as VERSION
from ..settings import Settings

class SubparserKeywords(TypedDict, total=False):
    """
    Keyword arguments acceptable for subcommands to register to a subparser of
    an argument parser.
    """

    help: Optional[str]
    aliases: Sequence[str]
    description: Optional[str]
    epilog: Optional[str]
    prefix_chars: str
    fromfile_prefix_chars: Optional[str]
    add_help: bool
    allow_abbrev: bool

ArgumentT = TypeVar('ArgumentT')

class ArgumentKeywords(Generic[ArgumentT], TypedDict, total=False):
    """
    Keyword arguments acceptable for registering an argument to a subparser of
    an argument parser.
    """

    action: str
    nargs: Optional[Union[int, str]]
    const: ArgumentT
    default: Union[ArgumentT, str]
    type: Union[Callable[[str], ArgumentT], FileType]
    choices: Optional[Iterable[ArgumentT]]
    required: bool
    help: Optional[str]
    metavar: Optional[Union[str, tuple[str, ...]]]
    dest: Optional[str]

ArgumentSpec = tuple[Union[str, tuple[str, ...]], ArgumentKeywords]
SubparserArguments = Iterable[ArgumentSpec]

class _SubcommandHolder(Namespace): # pylint: disable=too-few-public-methods
    subcommand: str = ''
    log: str = 'INFO'

class Base(Namespace):
    """
    Abstract command handling.
    """

    _commands: dict[str, type['Base']] = {}
    program: str = NAME
    subcommand: str = ''
    subparser_keywords: SubparserKeywords = {}
    subparser_arguments: SubparserArguments = []

    @classmethod
    def register(cls, name: str) -> Callable[[type['Base']], type['Base']]:
        """
        Register a subcommand.
        """

        def decorator(subclass: type['Base']) -> type['Base']:
            cls._commands[name] = subclass
            subclass.subcommand = name
            return subclass

        return decorator

    @classmethod
    def get_command(cls, name: str) -> 'Base':
        """
        Create a command instance for the given subcommand name.
        """

        return cls._commands[name]()

    @classmethod
    def register_arguments(cls) -> ArgumentParser:
        """
        Create an argument parser for all registered subcommands.
        """

        parser = ArgumentParser(prog=cls.program,
                                description='Receipt cataloging hub')
        parser.add_argument('--version', action='version',
                            version=f'{NAME} {VERSION}')
        parser.add_argument('--log',
                            choices=[
                                "CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"
                            ],
                            default="INFO", help='Log level')
        subparsers = parser.add_subparsers(dest='subcommand',
                                           help='Subcommands')
        for name, subclass in cls._commands.items():
            subparser = subparsers.add_parser(name,
                                              **subclass.subparser_keywords)
            for (argument, keywords) in subclass.subparser_arguments:
                if isinstance(argument, str):
                    subparser.add_argument(argument, **keywords)
                else:
                    subparser.add_argument(*argument, **keywords)

        return parser

    @classmethod
    def start(cls, executable: str, argv: Sequence[str]) -> None:
        """
        Parse arguments from a sequence of command line arguments and determine
        which command to run, register any arguments to it and finally execute
        the action of the command.
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
            return

        holder = _SubcommandHolder()
        parser.parse_known_args(argv[1:], namespace=holder)

        logging.getLogger(NAME).setLevel(getattr(logging, holder.log, 0))

        command = cls.get_command(holder.subcommand)
        command.program = cls.program
        command.subcommand = holder.subcommand
        parser.parse_args(argv[1:], namespace=command)
        command.run()

    def __init__(self) -> None:
        super().__init__()
        self.settings = Settings.get_settings()
        self.logger = logging.getLogger(self.__class__.__module__)

    def run(self) -> None:
        """
        Execute the command.
        """

        raise NotImplementedError('Must be implemented by subclasses')

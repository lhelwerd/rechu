"""
Base for receipt subcommands.
"""

from typing import Callable
from ..settings import Settings

class Base:
    """
    Abstract command handling.
    """

    _commands: dict[str, type['Base']] = {}

    @classmethod
    def register(cls, name: str) -> Callable[[type['Base']], type['Base']]:
        """
        Register a subcommand.
        """

        def decorator(subclass: type['Base']) -> type['Base']:
            cls._commands[name] = subclass
            return subclass

        return decorator

    @classmethod
    def get_command(cls, name: str) -> 'Base':
        """
        Create a command instance for the given subcommand name.
        """

        return cls._commands[name]()

    def __init__(self) -> None:
        self.settings = Settings.get_settings()

    def run(self) -> None:
        """
        Execute the command.
        """

        raise NotImplementedError('Must be implemented by subclasses')

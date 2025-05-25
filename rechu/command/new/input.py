"""
Input source for new subcommand.
"""

from datetime import datetime
import logging
import sys
from typing import Optional, Sequence, TextIO, TypeVar, Union, TYPE_CHECKING
try:
    import readline
except ImportError:
    if not TYPE_CHECKING:
        readline = None
import dateutil.parser

Input = Union[str, int, float]
InputT = TypeVar('InputT', bound=Input)

class InputSource:
    """
    Abstract base class for a typed input source.
    """

    def get_input(self, name: str, input_type: type[InputT],
                  options: Optional[str] = None) -> InputT:
        """
        Retrieve an input cast to a certain type (string, integer or float).
        Optionally, the input source provides suggestions from a predefined
        completion source defined by the `options` name.
        """

        raise NotImplementedError('Input must be retrieved by subclasses')

    def get_date(self) -> datetime:
        """
        Retrieve a date input.
        """

        raise NotImplementedError('Date input be retrieved by subclasses')

    def get_output(self) -> TextIO:
        """
        Retrieve an output stream to write content to.
        """

        raise NotImplementedError('Output must be implemented by subclasses')

    def update_suggestions(self, suggestions: dict[str, list[str]]) -> None:
        """
        Include additional suggestion completion sources.
        """

    def get_completion(self, text: str, state: int) -> Optional[str]:
        """
        Retrieve a completion option for the current suggestions and text state.
        The `text` is a partial input that matches some part of the suggestions
        and `state` indicates the position of the suggestion in the sorted
        list of matching suggestions to choose.

        If there is no match found or if the input source does not support
        completion suggestions, then `None` is returned.
        """

        raise NotImplementedError('Should be implemented by subclasses')

class Prompt(InputSource):
    """
    Standard input prompt.
    """

    def __init__(self) -> None:
        self._suggestions: dict[str, list[str]] = {}
        self._options: list[str] = []
        self._matches: list[str] = []
        self.register_readline()

    def get_input(self, name: str, input_type: type[InputT],
                  options: Optional[str] = None) -> InputT:
        """
        Retrieve an input cast to a certain type (string, integer or float).
        """

        if options is not None and options in self._suggestions:
            self._options = self._suggestions[options]
        else:
            self._options = []

        value: Optional[Input] = None
        while not isinstance(value, input_type):
            try:
                value = input_type(input(f'{name}: '))
            except ValueError as e:
                logging.warning('Invalid %s: %s', input_type.__name__, e)
        return value

    def get_date(self) -> datetime:
        date_value: Optional[datetime] = None
        while not isinstance(date_value, datetime):
            try:
                date_value = dateutil.parser.parse(self.get_input('Date', str))
            except ValueError as e:
                logging.warning('Invalid timestamp: %s', e)
        return date_value

    def get_output(self) -> TextIO:
        return sys.stdout

    def update_suggestions(self, suggestions: dict[str, list[str]]) -> None:
        self._suggestions.update(suggestions)

    def get_completion(self, text: str, state: int) -> Optional[str]:
        if state == 0:
            if text == '':
                self._matches = self._options
            else:
                self._matches = [
                    option for option in self._options
                    if option.startswith(text)
                ]
        try:
            return self._matches[state]
        except IndexError:
            return None

    def display_matches(self, substitution: str, matches: Sequence[str],
                        longest_match_length: int) -> None:
        """
        Write a display of matches to the standard output compatible with
        readline buffers.
        """

        line_buffer = readline.get_line_buffer()
        output = self.get_output()
        print(file=output)

        length = int(max(map(len, matches), default=longest_match_length) * 1.2)
        template = f"{{:<{length}}}"
        buffer = ""
        for match in matches:
            display = template.format(match[len(substitution):])
            if buffer != "" and len(buffer + display) > 80:
                print(buffer, file=output)
                buffer = ""
            buffer += display

        if buffer:
            print(buffer, file=output)

        print("> ", end="", file=output)
        print(line_buffer, end="", file=output)
        output.flush()

    def register_readline(self) -> None:
        """
        Register completion method to the `readline` module.
        """

        if readline is not None: # pragma: no cover
            readline.set_completer_delims('\t\n;')
            readline.set_completer(self.get_completion)
            readline.set_completion_display_matches_hook(self.display_matches)
            readline.parse_and_bind('tab: complete')
            readline.parse_and_bind('bind ^I rl_complete')

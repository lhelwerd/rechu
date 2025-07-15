"""
Tests for receipt subcommand base.
"""

from argparse import ArgumentParser
import logging
import os
from pathlib import Path
from typing import Optional
from unittest.mock import DEFAULT, MagicMock, call, patch
from rechu import __name__ as NAME, __version__ as VERSION
from rechu.command.base import Base
from ..settings import SettingsTestCase

@Base.register("test")
class TestCommand(Base):
    """
    Example subcommand.
    """

    latest_object: Optional['TestCommand'] = None
    subparser_keywords = {'help': 'Test command'}
    subparser_arguments = [
        ('fool', {'type': int, 'help': 'ABC'}),
        (('-b', '--bar'), {'dest': 'bizarre'})
    ]
    fool: int
    bizarre: str

    def run(self) -> None:
        self.__class__.latest_object = self

class BaseTest(SettingsTestCase):
    """
    Tests for abstract command handling.
    """

    def tearDown(self) -> None:
        super().tearDown()
        # Reset logging level
        logging.getLogger(NAME).setLevel(logging.NOTSET)

    def test_get_command(self) -> None:
        """
        Test creating a command instance.
        """

        test = Base.get_command("test")
        self.assertIsInstance(test, TestCommand)

    @patch("rechu.command.base.ArgumentParser")
    def test_register_arguments(self, parser: MagicMock) -> None:
        """
        Test creating an argument parser for all registered subcommands.
        """

        Base.register_arguments()
        parser.assert_called_once_with(prog='rechu',
                                       description='Receipt cataloging hub')
        main = parser.return_value
        main.add_argument.assert_has_calls([
            call('--version', action='version', version=f'rechu {VERSION}'),
            call('--log', choices=[
                "CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"
            ], default="INFO", help="Log level")
        ])
        main.add_subparsers.assert_called_once_with(dest='subcommand',
                                                    help='Subcommands')
        subparsers = main.add_subparsers.return_value
        subparsers.add_parser.assert_called_with('test', help='Test command')
        subparser = subparsers.add_parser.return_value
        subparser.add_argument.assert_has_calls([
            call('fool', type=int, help='ABC'),
            call('-b', '--bar', dest='bizarre')
        ])

    @patch.multiple(ArgumentParser, print_usage=DEFAULT, print_help=DEFAULT,
                    exit=DEFAULT)
    def test_start(self, **mocks: MagicMock) -> None:
        """
        Test parsing command line arguments, registering them to a command and
        executing the action of the command.
        """

        Base.start("python", ["env/bin/rechu"])
        self.assertEqual(Base.program, "rechu")
        mocks['print_usage'].assert_called_once_with()

        Base.start(str(Path(os.get_exec_path()[0], "python")),
                   ["rechu/__main__.py", "test", "--help"])
        self.assertEqual(Base.program, "python -m rechu")
        mocks['print_help'].assert_called()
        mocks['exit'].assert_called()

        Base.start("env/bin/python",
                   ["rechu/__main__.py", "test", "1234", "-b", "qux"])
        self.assertEqual(Base.program, "env/bin/python -m rechu")
        if TestCommand.latest_object is None:
            self.fail("Unexpected missing latest command object")
        self.assertEqual(TestCommand.subcommand, "test")
        self.assertEqual(TestCommand.latest_object.fool, 1234)
        self.assertEqual(TestCommand.latest_object.bizarre, "qux")

        mocks['print_usage'].reset_mock()
        mocks['exit'].reset_mock()

        Base.start("env/bin/python",
                   ["rechu/__main__.py", "test", "--fake-argument"])
        mocks['print_usage'].assert_called()
        mocks['exit'].assert_called()

    def test_run(self) -> None:
        """
        Test executing a command.
        """

        base = Base()
        with self.assertRaises(NotImplementedError):
            base.run()

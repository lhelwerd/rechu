"""
Tests for input source of new subcommand.
"""

from datetime import datetime
from io import StringIO
import unittest
from unittest.mock import patch
from rechu.command.new import InputSource, Prompt
from . import INPUT_MODULE

class InputSourceTest(unittest.TestCase):
    """
    Tests for abstract base class of an input source.
    """

    def setUp(self) -> None:
        self.input = InputSource()

    def test_get_input(self) -> None:
        """
        Test retrieving an input.
        """

        with self.assertRaises(NotImplementedError):
            self.input.get_input("foo", str, "test")

    def test_get_date(self) -> None:
        """
        Test retrieving a date input.
        """

        with self.assertRaises(NotImplementedError):
            self.input.get_date()

    def test_get_output(self) -> None:
        """
        Test retrieving an output stream.
        """

        with self.assertRaises(NotImplementedError):
            self.input.get_output()

    def test_get_completion(self) -> None:
        """
        Test retrieving a completion option for the current suggestions.
        """

        with self.assertRaises(NotImplementedError):
            self.input.get_completion("foo", 0)

class PromptTest(unittest.TestCase):
    """
    Tests for standard input prompt.
    """

    def test_get_input(self) -> None:
        """
        Test retrieving an input.
        """

        prompt = Prompt()
        with patch(f"{INPUT_MODULE}.input", return_value="foobar"):
            self.assertEqual(prompt.get_input("foo", str), "foobar")
        with patch(f"{INPUT_MODULE}.input", return_value="9.99"):
            self.assertEqual(prompt.get_input("foo", float), 9.99)
        with patch(f"{INPUT_MODULE}.input", return_value="10"):
            self.assertEqual(prompt.get_input("foo", int), 10)
        with patch(f"{INPUT_MODULE}.input", return_value=""):
            self.assertEqual(prompt.get_input("foo", str), "")
            self.assertEqual(prompt.get_input("foo", str, default="baz"), "baz")
            self.assertEqual(prompt.get_input("foo", int, default=42), 42)

    def test_get_date(self) -> None:
        """
        Test retrieving a date input.
        """

        prompt = Prompt()
        date = datetime(2025, 6, 9, 0, 0, 0)
        with patch(f"{INPUT_MODULE}.input", return_value="2025-06-09"):
            self.assertEqual(prompt.get_date(), date)
        with patch(f"{INPUT_MODULE}.input", return_value=""):
            self.assertEqual(prompt.get_date(default=date), date)
        with patch(f"{INPUT_MODULE}.input", return_value="12:34"):
            default = datetime(2025, 6, 9, 3, 12, 0)
            self.assertEqual(prompt.get_date(default=default),
                             datetime(2025, 6, 9, 12, 34, 0))

    def test_get_completion(self) -> None:
        """
        Test retrieving a completion option for the current suggestions.
        """

        prompt = Prompt()
        self.assertIsNone(prompt.get_completion("foo", 0))

        prompt.update_suggestions({"test": ["barbaz", "foobar", "foobaz"]})
        with patch(f"{INPUT_MODULE}.input", return_value="foobar"):
            prompt.get_input("qux", str, options="test")
        self.assertEqual(prompt.get_completion("", 0), "barbaz")
        self.assertEqual(prompt.get_completion("", 1), "foobar")
        self.assertEqual(prompt.get_completion("", 2), "foobaz")
        self.assertIsNone(prompt.get_completion("", 3))

        self.assertEqual(prompt.get_completion("foo", 0), "foobar")
        self.assertEqual(prompt.get_completion("foo", 1), "foobaz")
        self.assertIsNone(prompt.get_completion("foo", 2))

    @patch('sys.stdout', new_callable=StringIO)
    def test_display_matches(self, stdout: StringIO) -> None:
        """
        Test displaying matches compatible with readline buffers.
        """

        prompt = Prompt()
        prompt.display_matches("nothing", [], 0)
        self.assertEqual(stdout.getvalue(), "\n> ")

        stdout.seek(0)
        stdout.truncate()

        prompt.display_matches("foo", ["foobar", "foobaz"], 6)
        self.assertEqual(stdout.getvalue(), "\nbar    baz    \n> ")

        stdout.seek(0)
        stdout.truncate()

        prompt.display_matches("foo", [f"foo{'bar' * 27}", f"foo{'baz' * 27}"],
                               86)
        space = ' ' * 19
        self.assertEqual(stdout.getvalue(),
                         f"\n{'bar' * 27}{space}\n{'baz' * 27}{space}\n> ")

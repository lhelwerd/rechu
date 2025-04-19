"""
Tests of subcommand to create a new receipt YAML file and import it.
"""

from datetime import datetime
from io import StringIO
from pathlib import Path
import unittest
from unittest.mock import patch
from sqlalchemy import select
import yaml
from rechu.command.new import New, InputSource, Prompt, Step
from rechu.models.base import Price
from rechu.models.receipt import Receipt
from ..database import DatabaseTestCase

class NewTest(DatabaseTestCase):
    """
    Test creating a YAML file and importing it to the database.
    """

    path = Path("samples/2024-11-01-12-34-id.yml")

    def tearDown(self) -> None:
        super().tearDown()
        self.path.unlink(missing_ok=True)

    def test_run(self) -> None:
        """
        Test executing the command.
        """

        with open("samples/receipt.yml", "r", encoding="utf-8") as receipt_file:
            expected_receipt = yaml.safe_load(receipt_file)
            # Drop missing discount product label
            expected_receipt['bonus'][-1].pop()

        with open("samples/receipt_input", "r", encoding="utf-8") as input_file:
            with patch("rechu.command.new.input",
                       side_effect=[line.rstrip() for line in input_file]):
                command = New()
                command.run()
                with self.database as session:
                    receipt = session.scalars(select(Receipt)).first()
                    if receipt is None:
                        self.fail("Expected receipt to be stored")
                    self.assertEqual(receipt.filename, self.path.name)

                    self.assertTrue(self.path.exists())
                    mtime = self.path.stat().st_mtime
                    self.assertEqual(datetime.fromtimestamp(mtime),
                                     receipt.updated)
                    with self.path.open("r", encoding="utf-8") as new_file:
                        new_receipt = yaml.safe_load(new_file)
                        self.assertEqual(expected_receipt, new_receipt)

    def test_run_invalid(self) -> None:
        """
        Test executing the command with invalid inputs.
        """

        with patch("rechu.command.new.input",
                   side_effect=["invalid date", "2024-11-01 12:34", "id", "0",
                                "", "products", "?", "discounts", "?", "w",
                                "quit"]):
            command = New()
            command.run()
            with self.database as session:
                self.assertIsNone(session.scalars(select(Receipt)).first())
            self.assertFalse(self.path.exists())

        with patch("rechu.command.new.input",
                   side_effect=["2024-11-01 12:34", "id", "foo", "bar", "baz",
                                "0.01", "", "0", "disco", "-0.01", "?", "w"]):
            command = New()
            command.run()
            with self.database as session:
                receipt = session.scalars(select(Receipt)).first()
                if receipt is None:
                    self.fail("Expected receipt to be stored")
                self.assertEqual(receipt.filename, self.path.name)
                self.assertEqual(len(receipt.products), 1)
                self.assertEqual(receipt.products[0].price, Price('0.01'))

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

    def test_get_completion(self) -> None:
        """
        Test retrieving a completion option for the current suggestions.
        """

        prompt = Prompt()
        self.assertIsNone(prompt.get_completion("foo", 0))

        prompt.update_suggestions({"test": ["barbaz", "foobar", "foobaz"]})
        with patch("rechu.command.new.input", return_value="foobar"):
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

class StepTest(unittest.TestCase):
    """
    Tests for abstract base class of a receipt creation step.
    """

    def test_run(self):
        """
        Test performing the step.
        """

        with self.assertRaises(NotImplementedError):
            Step(Receipt(), Prompt()).run()

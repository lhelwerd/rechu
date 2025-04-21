"""
Tests of subcommand to create a new receipt YAML file and import it.
"""

from collections.abc import Generator, Iterable
from contextlib import contextmanager
from datetime import datetime
from io import StringIO
import os
from pathlib import Path
from subprocess import CalledProcessError
import unittest
from unittest.mock import MagicMock, call, patch
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

    edit = Path("samples/receipt_edit_input")
    expected = Path("samples/receipt.yml")
    create = Path("samples/2024-11-01-12-34-id.yml")
    copy = Path("samples/2024-11-01-00-00-id.yml")

    def tearDown(self) -> None:
        super().tearDown()
        self.create.unlink(missing_ok=True)
        self.copy.unlink(missing_ok=True)

    @contextmanager
    def _setup_input(self, input_path: Path,
                     extra_inputs: Iterable[str] = ()) -> Generator[MagicMock]:
        with input_path.open("r", encoding="utf-8") as input_file:
            inputs = [line.rstrip() for line in input_file] + list(extra_inputs)
            with patch("rechu.command.new.input", side_effect=inputs) as mock:
                yield mock

    def test_run(self) -> None:
        """
        Test executing the command.
        """

        with self._setup_input(Path("samples/receipt_input")):
            command = New()
            command.run()
            self._compare_expected_receipt(self.create)

    def _compare_expected_receipt(self, path: Path) -> None:
        with self.expected.open("r", encoding="utf-8") as receipt_file:
            expected_receipt = yaml.safe_load(receipt_file)
            # Drop missing discount product label
            expected_receipt['bonus'][-1].pop()

        with self.database as session:
            receipt = session.scalars(select(Receipt)).first()
            if receipt is None:
                self.fail("Expected receipt to be stored")
            self.assertEqual(receipt.filename, path.name)

            self.assertTrue(path.exists())
            mtime = path.stat().st_mtime
            self.assertEqual(datetime.fromtimestamp(mtime),
                             receipt.updated)
            with path.open("r", encoding="utf-8") as new_file:
                new_receipt = yaml.safe_load(new_file)
                self.assertEqual(expected_receipt, new_receipt)

    def _check_no_receipt(self, path: Path) -> None:
        with self.database as session:
            self.assertIsNone(session.scalars(select(Receipt)).first())
        self.assertFalse(path.exists())

    def _copy_file(self, args: list[str], check: bool = False) -> None:
        # pylint: disable=unused-argument
        with self.expected.open('r', encoding='utf-8') as input_file:
            with Path(args[-1]).open('w', encoding='utf-8') as tmp_file:
                tmp_file.write(input_file.read())

    @staticmethod
    def _clear_file(args: list[str], check: bool = False) -> None:
        # pylint: disable=unused-argument
        with Path(args[-1]).open('w', encoding='utf-8') as tmp_file:
            tmp_file.write('')

    def test_run_edit_clear(self) -> None:
        """
        Test executing the command with an edit in between that clears the file.
        """

        with self._setup_input(self.edit, ["quit"]):
            with patch("subprocess.run", side_effect=self._clear_file) as clear:
                command = New()
                command.run()
                clear.assert_called_once()
                self._check_no_receipt(self.copy)

    def test_run_edit_no_editor(self) -> None:
        """
        Test executing the command with an edit in between but with no editor
        in the PATH.
        """

        with self._setup_input(self.edit, ["quit"]):
            with patch("subprocess.run", side_effect=self._copy_file) as copy:
                environment = {
                    'RECHU_DATA_EDITOR': '/usr/bin/unittest edit -c 1',
                    'EDITOR': 'nano'
                }
                with patch.dict("os.environ", environment):
                    os.environ.pop('VISUAL', None)
                    with patch("shutil.which", return_value=None) as which:
                        command = New()
                        command.run()
                        copy.assert_not_called()
                        self.assertEqual(which.call_args_list, [
                            call("/usr/bin/unittest"), call("nano"),
                            call("editor"), call("vim")
                        ])
                        self._check_no_receipt(self.copy)

    def test_run_edit_error(self) -> None:
        """
        Test executing the command with an edit in between where the editor
        executable has a non-zero exit status.
        """

        with patch.dict('os.environ', {'RECHU_DATA_EDITOR': '/bin/ut ed -c 1'}):
            with self._setup_input(self.edit, ["quit"]):
                error = CalledProcessError(1, '/bin/ut')
                with patch("subprocess.run", side_effect=error) as run:
                    with patch("shutil.which", return_value='/bin/ut'):
                        command = New()
                        command.run()
                        run.assert_called_once()
                        self.assertEqual(run.call_args.args[0][:-1],
                                         ['/bin/ut', 'ed', '-c', '1'])
                        self._check_no_receipt(self.copy)

    def test_run_edit(self) -> None:
        """
        Test executing the command with an edit in between.
        """

        with self._setup_input(self.edit, ["w"]):
            with patch("subprocess.run", side_effect=self._copy_file) as copy:
                command = New()
                command.run()
                copy.assert_called_once()
                self._compare_expected_receipt(self.copy)

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
            self._check_no_receipt(self.create)

        # Some invalid inputs but in the end provides a valid receipt
        with patch("rechu.command.new.input",
                   side_effect=["2024-11-01 12:34", "id", "foo", "bar", "baz",
                                "0.01", "", "0", "disco", "-0.01", "?", "h",
                                "w", "n", "w", "y"]):
            command = New()
            command.confirm = True
            command.run()
            with self.database as session:
                receipt = session.scalars(select(Receipt)).first()
                if receipt is None:
                    self.fail("Expected receipt to be stored")
                self.assertEqual(receipt.filename, self.create.name)
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

    def test_description(self):
        """
        Test retreiving a usage message of the step.
        """

        with self.assertRaises(NotImplementedError):
            self.assertEqual(Step(Receipt(), Prompt()).description, "")

"""
Tests for command entry point.
"""

from io import StringIO
from unittest.mock import patch

from rechu import __name__ as NAME, __version__ as VERSION
from rechu.__main__ import main

from .settings import SettingsTestCase


class MainTest(SettingsTestCase):
    """
    Tests for main entry point for receipt subcommands.
    """

    @patch("sys.stdout", new_callable=StringIO)
    def test_main(self, stdout: StringIO) -> None:
        """
        Test main entry point.
        """

        with patch("sys.argv", [NAME]):
            self.assertEqual(main(), 1)
            self.assertTrue(stdout.getvalue().startswith(f"usage: {NAME}"))

        _ = stdout.seek(0)
        _ = stdout.truncate()

        with patch("sys.argv", [NAME, "--version"]):
            with self.assertRaises(SystemExit):
                self.assertEqual(main(), 0)
            self.assertEqual(stdout.getvalue(), f"{NAME} {VERSION}\n")

"""
Tests of subcommand to generate an amalgamte settings file.
"""

from typing import final
from pathlib import Path
from unittest.mock import patch
from io import StringIO
from rechu.command.config import Config
from ..settings import SettingsTestCase, patch_settings


@final
class ConfigTest(SettingsTestCase):
    """
    Test obtaining settings file representation.
    """

    @patch("sys.stdout", new_callable=StringIO)
    @patch_settings({"RECHU_DATA_PATH": "/foo"})
    def test_run(self, stdout: StringIO) -> None:
        """
        Test executing the command.
        """

        config = Config()
        config.run()

        lines = stdout.getvalue().split("\n")
        data = lines.index("[data]")
        db = lines.index("[database]")
        self.assertLess(data, db)
        self.assertFalse(any(line.startswith("[") for line in lines[:data]))
        self.assertFalse(
            any(line.startswith("[") for line in lines[data + 1 : db])
        )
        self.assertFalse(any(line.startswith("[") for line in lines[db + 1 :]))
        self.assertEqual(lines[data + 1 : db].count('path = "/foo"'), 1)
        self.assertEqual(lines[data + 1 : db].count('pattern = "samples"'), 1)
        self.assertEqual(lines[db + 1 :].count('foreign_keys = "ON"'), 1)
        self.assertEqual(lines[db + 1 :].count('_custom_prop = "ignore"'), 1)

        _ = stdout.seek(0)
        _ = stdout.truncate()

        config.section = "missing"
        config.run()
        self.assertEqual(stdout.getvalue(), "\n")

        _ = stdout.seek(0)
        _ = stdout.truncate()

        config.section = "_other"
        config.run()
        self.assertEqual(stdout.getvalue(), "\n")

        _ = stdout.seek(0)
        _ = stdout.truncate()

        config.section = "database"
        config.run()

        database = stdout.getvalue().split("\n")
        self.assertEqual(database, lines[db:])

        _ = stdout.seek(0)
        _ = stdout.truncate()

        config.key = "?"
        config.run()

        self.assertEqual(stdout.getvalue(), "\n")

        _ = stdout.seek(0)
        _ = stdout.truncate()

        config.key = "_custom_prop"
        config.run()

        self.assertEqual(
            stdout.getvalue(),
            """[database]
# Some property that does not exist in the fallbacks.
_custom_prop = "ignore"

""",
        )

        _ = stdout.seek(0)
        _ = stdout.truncate()

        defaults_path = Path("rechu/settings.toml")
        defaults = Config()
        defaults.file = str(defaults_path)
        defaults.run()

        with defaults_path.open("r", encoding="utf-8") as defaults_file:
            self.assertEqual(stdout.getvalue(), f"{defaults_file.read()}\n")

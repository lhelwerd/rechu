"""
Tests of subcommand to run Alembic commands for database migration.
"""

from io import StringIO
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch
from rechu.command.alembic import Alembic
from rechu.database import Database

class AlembicTest(unittest.TestCase):
    """
    Test running an alembic command.
    """

    @patch("rechu.command.alembic.config")
    def test_run(self, config: MagicMock) -> None:
        """
        Test executing the command.
        """

        path = str(Path("rechu/alembic.ini").resolve())

        alembic = Alembic()
        alembic.run()
        config.main.assert_called_once_with(argv=["-c", path],
                                            prog="rechu alembic")

        config.main.reset_mock()

        alembic.args = ["-h"]
        alembic.run()
        config.main.assert_called_once_with(argv=["-c", path, "-h"],
                                            prog="rechu alembic")

        config.main.reset_mock()

        alembic.args = ["revision", "-m", "a"]
        alembic.run()
        config.main.assert_called_once_with(argv=["-c", path, "revision",
                                                  "--autogenerate", "-m", "a"],
                                            prog="rechu alembic")

    def test_downgrade_upgrade(self) -> None:
        """
        Test downgrading and upgrading the database.
        """

        database = Database()
        database.create_schema()

        alembic = Alembic()
        alembic.args = ["downgrade", "base"]
        alembic.run()

        alembic.args = ["upgrade", "--sql", "head"]
        with patch("sys.stdout", new_callable=StringIO) as stdout:
            alembic.run()
            self.assertNotEqual(stdout.getvalue(), '')

        alembic.args = ["upgrade", "head"]
        alembic.run()

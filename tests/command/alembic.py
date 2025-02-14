"""
Tests of subcommand to run Alembic commands for database migration.
"""

from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch
from sqlalchemy import create_mock_engine
from rechu.command.alembic import Alembic
from ..database import DatabaseTestCase

class AlembicTest(DatabaseTestCase):
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

        alembic = Alembic()
        alembic.args = ["downgrade", "base"]
        alembic.run()

        alembic.args = ["upgrade", "head"]
        alembic.run()

        alembic.args = ["upgrade", "--sql", "base:head"]
        with self.assertRaises(SystemExit):
            with patch("sys.stdout", new_callable=StringIO) as stdout:
                alembic.run()
                self.assertIn("Offline mode currently not supported for SQLite",
                              stdout)

        url = "postgresql+psycopg://"
        engine = create_mock_engine(url, MagicMock())
        setattr(engine, 'url', url)
        with patch('rechu.database.Database',
                   return_value=MagicMock(engine=engine)):
            with patch("sys.stdout", new_callable=StringIO) as stdout:
                alembic.run()
                self.assertNotEqual(stdout.getvalue(), '')

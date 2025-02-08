"""
Tests of subcommand to run Alembic commands for database migration.
"""

from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch
from rechu.command.alembic import Alembic

class AlembicTest(unittest.TestCase):
    """
    Test running an alembic command.
    """

    @patch("rechu.command.alembic.config")
    def test_run(self, config: MagicMock) -> None:
        """
        Test executing the command.
        """

        alembic = Alembic()
        path = Path("rechu/alembic.ini").resolve()
        with patch("sys.argv", new=["rechu", "alembic"]):
            alembic.run()
            config.main.assert_called_once_with(argv=["-c", str(path), ""],
                                                prog="rechu alembic")

        config.main.reset_mock()

        with patch("sys.argv", new=["rechu", "alembic", "revision", "-m", "a"]):
            alembic.run()
            config.main.assert_called_once_with(argv=["-c", str(path),
                                                      "revision",
                                                      "--autogenerate",
                                                      "-m", "a"],
                                                prog="rechu alembic")

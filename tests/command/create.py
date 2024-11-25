"""
Tests of database schema creation subcommand.
"""

from sqlalchemy import inspect
from rechu.command.create import Create
from rechu.database import Database
from ..settings import SettingsTestCase

class CreateTest(SettingsTestCase):
    """
    Test creating the database with the database schema.
    """

    def test_run(self) -> None:
        """
        Test executing the command.
        """

        command = Create()
        command.run()
        database = Database()
        inspector = inspect(database.engine)
        self.assertIsNot(inspector.get_table_names(), [])

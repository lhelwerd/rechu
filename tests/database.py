"""
Tests for database access.
"""

from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch
from alembic import command
from sqlalchemy import select, Table
from sqlalchemy.exc import OperationalError
from rechu.database import Database
from rechu.models.base import Base
from rechu.models.receipt import Receipt, DiscountItems
from .settings import SettingsTestCase

class DatabaseTestCase(SettingsTestCase):
    """
    Test case base class which creates and drops the database between tests.
    """

    def setUp(self) -> None:
        super().setUp()
        self.database = Database()
        self.database.create_schema()

    def tearDown(self) -> None:
        super().tearDown()
        self.database.drop_schema()

class DatabaseTest(DatabaseTestCase):
    """
    Tests for database provider.
    """

    def test_enter(self) -> None:
        """
        Test context statement.
        """

        with self.database as session:
            self.assertIsNotNone(session.get_bind())
            self.assertIsNotNone(session.connection())
            with self.assertRaises(RuntimeError):
                with self.database as session:
                    pass

        self.assertIsNone(self.database.session)

    def test_close(self) -> None:
        """
        Test closing the session.
        """

        self.database.close()
        self.assertIsNone(self.database.session)
        with self.database as session:
            self.assertIsNotNone(self.database.session)
            self.assertEqual(session, self.database.session)
            self.database.close()
            self.assertIsNone(self.database.session)

    def test_create_schema(self) -> None:
        """
        Test performing schema creation.
        """

        # First ensure the database is empty.
        self.database.drop_schema()

        self.database.create_schema()
        # Check if a model's table is empty but existing.
        with self.database as session:
            self.assertEqual(list(session.scalars(select(Receipt))), [])
        # Check alembic stamped version.
        stdout = StringIO()
        command.current(self.database.get_alembic_config(stdout=stdout))
        self.assertIn("head", stdout.getvalue())

    def test_drop_schema(self) -> None:
        """
        Test cleaning up the database by removing all model tables.
        """

        self.database.drop_schema()
        with self.assertRaisesRegex(OperationalError, "no such table: receipt"):
            with self.database as session:
                self.assertNotEqual(list(session.scalars(select(Receipt))), [])

    def test_get_alembic_config(self) -> None:
        """
        Test retrieving an alembic configuration object preconfigured for rechu.
        """

        self.assertEqual(self.database.get_alembic_config().config_file_name,
                         Path("rechu/alembic.ini").resolve())

    @patch("rechu.database.context")
    def test_offline_table(self, context: MagicMock) -> None:
        """
        Test retrieving a table reerence when running alembic migration in
        offline mode.
        """

        mock_keywords: dict[str, bool] = {'is_offline_mode.return_value': False}
        context.configure_mock(**mock_keywords)
        self.assertIsNone(Database.offline_table(Receipt))

        mock_keywords = {'is_offline_mode.return_value': True}
        context.configure_mock(**mock_keywords)
        self.assertIsInstance(Database.offline_table(Receipt), Table)
        self.assertIsInstance(Database.offline_table(DiscountItems), Table)

        self.assertIsNone(Database.offline_table(Base))

"""
Tests for database access.
"""

from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch
from alembic import command
from sqlalchemy import create_mock_engine, event, inspect, select, text
from sqlalchemy.exc import DatabaseError
from rechu.database import Database
from rechu.models import Product, Receipt
from rechu.settings import Settings
from .settings import SettingsTestCase

class DatabaseTestCase(SettingsTestCase):
    """
    Test case base class which creates and drops the database between tests.
    """

    def setUp(self) -> None:
        super().setUp()
        self.database = Database()
        self.database.drop_schema()
        self.database.create_schema()

    def tearDown(self) -> None:
        super().tearDown()
        self.database.drop_schema()
        self.database.close()

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
        inspector = inspect(self.database.engine)
        self.assertNotEqual(inspector.get_table_names(), [])
        # Check if our models' tables are empty but existing.
        with self.database as session:
            self.assertEqual(list(session.scalars(select(Receipt))), [])
            self.assertEqual(list(session.scalars(select(Product))), [])
        # Check alembic stamped version.
        stdout = StringIO()
        command.current(self.database.get_alembic_config(stdout=stdout))
        self.assertIn("head", stdout.getvalue())

    def test_drop_schema(self) -> None:
        """
        Test cleaning up the database by removing all model tables.
        """

        self.database.drop_schema()
        with self.assertRaisesRegex(DatabaseError, "receipt"):
            with self.database as session:
                self.assertNotEqual(list(session.scalars(select(Receipt))), [])

    def test_get_alembic_config(self) -> None:
        """
        Test retrieving an alembic configuration object preconfigured for rechu.
        """

        self.assertEqual(self.database.get_alembic_config().config_file_name,
                         Path("rechu/alembic.ini").resolve())

    @patch.dict('os.environ',
                {'RECHU_DATABASE_URI': 'sqlite+pysqlite:///example.db'})
    def test_set_sqlite_pragma(self) -> None:
        """
        Test whether the SQLite dialect is set to enable foreign keys.
        """

        Settings.clear()

        database = Database()
        with database as session:
            self.assertTrue(session.scalar(text('PRAGMA foreign_keys')))

        database.clear()
        Settings.clear()

        with patch.dict('os.environ', {'RECHU_DATABASE_FOREIGN_KEYS': 'off'}):
            database = Database()
            with database as session:
                self.assertFalse(session.scalar(text('PRAGMA foreign_keys')))

        database.clear()
        Settings.clear()

        url = "postgresql+psycopg://"
        engine = create_mock_engine(url, MagicMock())
        setattr(engine, 'url', url)
        with patch('rechu.database.create_engine', return_value=engine):
            with patch('rechu.database.event', wraps=event) as wrapped_event:
                database = Database()
                wrapped_event.listen.assert_not_called()
                database.clear()
                wrapped_event.contains.assert_called()
                wrapped_event.remove.assert_not_called()

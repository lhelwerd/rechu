"""
Tests for database access.
"""

from rechu.database import Database
from .settings import SettingsTestCase

class DatabaseTest(SettingsTestCase):
    """
    Tests for database provider.
    """

    def setUp(self) -> None:
        super().setUp()
        self.database = Database()

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

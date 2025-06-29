"""
Tests of subcommand to run Alembic commands for database migration.
"""

from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch
from alembic import command
from sqlalchemy import create_mock_engine, select
from rechu.command.alembic import Alembic
from rechu.io.products import ProductsReader
from rechu.io.receipt import ReceiptReader
from rechu.models import Product, Receipt
from rechu.settings import Settings
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

        # Check if there are no outstanding database changes (same as model).
        command.check(self.database.get_alembic_config())

    def test_downgrade_upgrade_data(self) -> None:
        """
        Test downgrading and upgrading the database with data in it.
        """

        with self.database as session:
            products_path = Path("samples/products-id.yml")
            products = list(ProductsReader(products_path).read())
            session.add_all(products)
            receipt_path = Path("samples/receipt.yml")
            session.add(next(ReceiptReader(receipt_path).read()))

        alembic = Alembic()
        alembic.args = ["downgrade", "base"]
        alembic.run()

        alembic.args = ["upgrade", "head"]
        alembic.run()

        with self.database as session:
            product_query = select(Product).filter(Product.generic_id.is_(None))
            self.assertEqual(len(session.scalars(product_query).all()),
                             len(products))
            self.assertIsNotNone(session.scalars(select(Receipt)).first())


    def test_upgrade_offline(self) -> None:
        """
        Test generating offline upgrade migration SQL scripts.
        """

        Settings.clear()
        self.database.clear()

        alembic = Alembic()
        alembic.args = ["upgrade", "--sql", "base:head"]

        with patch.dict('os.environ',
                        {'RECHU_DATABASE_URI': 'sqlite+pysqlite:///mock.db'}):
            with self.assertRaises(SystemExit):
                with patch("sys.stdout", new_callable=StringIO) as stdout:
                    alembic.run()
                    self.assertIn("Offline mode not supported for SQLite",
                                  stdout)

        self.database.clear()

        url = "postgresql+psycopg://"
        engine = create_mock_engine(url, MagicMock())
        setattr(engine, 'url', url)
        with patch('rechu.database.Database',
                   return_value=MagicMock(engine=engine)):
            with patch("sys.stdout", new_callable=StringIO) as stdout:
                alembic.run()
                self.assertNotEqual(stdout.getvalue(), '')

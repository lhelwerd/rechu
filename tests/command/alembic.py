"""
Tests of subcommand to run Alembic commands for database migration.
"""

from io import StringIO
import logging
from pathlib import Path
from typing import cast, final
from unittest.mock import MagicMock, patch
from alembic import command
from alembic.config import Config
from sqlalchemy import create_mock_engine, select
from typing_extensions import override
from rechu.command.alembic import Alembic
from rechu.database import Database
from rechu.io.products import ProductsReader
from rechu.io.receipt import ReceiptReader
from rechu.models import Product, Receipt
from rechu.settings import Settings
from ..database import DatabaseTestCase
from ..settings import patch_settings


@final
class AlembicTest(DatabaseTestCase):
    """
    Test running an alembic command.
    """

    @override
    def setUp(self) -> None:
        super().setUp()
        logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
        self.root_level = logging.getLogger(name=None).level

    @override
    def tearDown(self) -> None:
        super().tearDown()
        # Reset logging levels
        logging.getLogger(name=None).setLevel(self.root_level)
        for logger in ("sqlalchemy.engine", "alembic", "rechu"):
            logging.getLogger(name=logger).setLevel(logging.NOTSET)

    @patch("rechu.command.alembic.CommandLine")
    def test_run(self, alembic_cmd: MagicMock) -> None:
        """
        Test executing the command.
        """

        alembic = Alembic()
        alembic.run()
        alembic_cmd.assert_called_once_with(prog="rechu alembic")
        alembic_command = cast(MagicMock, alembic_cmd.return_value)
        parser = cast(MagicMock, alembic_command.parser)
        parse_args = cast(MagicMock, parser.parse_args)
        parse_args.assert_called_once_with([])
        run_cmd = cast(MagicMock, alembic_command.run_cmd)
        run_cmd.assert_called_once()

        alembic_cmd.reset_mock()

        alembic.args = ["-h"]
        alembic.run()
        alembic_cmd.assert_called_once_with(prog="rechu alembic")
        parse_args.assert_called_once_with(["-h"])
        run_cmd.assert_called_once()

        alembic_cmd.reset_mock()

        alembic.args = ["revision", "-m", "a"]
        alembic.run()
        alembic_cmd.assert_called_once_with(prog="rechu alembic")
        parse_args.assert_called_once_with(
            ["revision", "--autogenerate", "-m", "a"]
        )
        run_cmd.assert_called_once()

    @patch.object(Database, "get_alembic_config")
    def test_incomplete_config(self, get_config: MagicMock) -> None:
        """
        Test executing the command without a complete configuration file.
        """

        # Minimal necessary information
        get_config.return_value = Config("tests/alembic.ini")

        # No error raised
        alembic = Alembic()
        alembic.args = ["check"]
        alembic.run()

    @patch.object(Database, "get_alembic_config")
    def test_no_config(self, get_config: MagicMock) -> None:
        """
        Test executing the command without a configuration file.
        """

        # Minimal necessary information
        config = Config(file_=None)
        config.set_main_option("script_location", "rechu/alembic")
        get_config.return_value = config

        # No error raised
        alembic = Alembic()
        alembic.args = ["check"]
        alembic.run()

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
            self.assertEqual(
                len(session.scalars(product_query).all()), len(products)
            )
            self.assertIsNotNone(session.scalars(select(Receipt)).first())

    def test_upgrade_offline(self) -> None:
        """
        Test generating offline upgrade migration SQL scripts.
        """

        Settings.clear()
        self.database.clear()

        alembic = Alembic()
        alembic.args = ["upgrade", "--sql", "base:head"]

        with patch_settings(
            {"RECHU_DATABASE_URI": "sqlite+pysqlite:///mock.db"}
        ):
            with self.assertRaises(SystemExit):
                with patch("sys.stdout", new_callable=StringIO) as stdout:
                    alembic.run()
                    self.assertIn(
                        "Offline mode not supported for SQLite", stdout
                    )

        self.database.clear()

        url = "postgresql+psycopg://"
        engine = create_mock_engine(url, MagicMock())
        setattr(engine, "url", url)
        with patch(
            "rechu.database.Database", return_value=MagicMock(engine=engine)
        ):
            with patch("sys.stdout", new_callable=StringIO) as stdout:
                alembic.run()
                self.assertNotEqual(stdout.getvalue(), "")

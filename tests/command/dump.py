"""
Tests of subcommand to export database entries as YAML files.
"""

import os
import shutil
from datetime import datetime
from itertools import zip_longest
from pathlib import Path
from typing import final

from sqlalchemy import select
from typing_extensions import override

from rechu.command.dump import Dump
from rechu.io.products import ProductsReader
from rechu.io.receipt import ReceiptReader
from rechu.models.product import Product
from rechu.models.receipt import ProductItem

from ..database import DatabaseTestCase
from ..settings import patch_settings


@final
class DumpTest(DatabaseTestCase):
    """
    Test dumping YAML files from the database.
    """

    # Source data paths
    receipt = Path("samples/receipt.yml").resolve()
    products = Path("samples/products-id.yml")
    shops = Path("samples/shops.yml")

    # Temporary paths
    path = Path("tmp")
    copy = Path("samples/receipt-1.yml")

    @override
    def setUp(self) -> None:
        super().setUp()
        self.now = datetime.now()
        with self.database as session:
            for product in ProductsReader(self.products).read():
                session.add(product)
            session.add(
                next(ReceiptReader(self.receipt, updated=self.now).read())
            )
            self.copy.symlink_to(self.receipt.name)
            self.assertEqual(self.copy.resolve(), self.receipt)
            session.add(next(ReceiptReader(self.copy, updated=self.now).read()))

        # Product matching does not affect receipt dump attributes nor order
        with self.database as session:
            item = session.scalars(select(ProductItem)).first()
            if item is None:
                self.fail("Expected product item to be found in database")
            item.product = session.scalars(select(Product)).first()

    @override
    def tearDown(self) -> None:
        super().tearDown()
        shutil.rmtree(self.path, ignore_errors=True)
        self.copy.unlink(missing_ok=True)

    @patch_settings({"RECHU_DATA_PATH": "tmp"})
    def test_run(self) -> None:
        """
        Test executing the command.
        """

        now = self.now.timestamp()

        command = Dump()
        command.run()

        # Shops are written with the same filename pattern.
        shops_path = self.path / "samples" / "shops.yml"

        # Products are written with the same filename pattern.
        products_path = self.path / "samples" / "products-id.yml"

        # The original receipt filename is preferred over the date format.
        dump_path = self.path / "samples" / "receipt.yml"
        copy_path = self.path / "samples" / "receipt-1.yml"

        self.assertTrue(shops_path.exists())
        self.assertTrue(products_path.exists())
        self.assertTrue(dump_path.exists())
        self.assertTrue(copy_path.exists())

        # The timestamps are set to the receipt model updated time.
        self.assertEqual(dump_path.stat().st_mtime, now)
        self.assertEqual(copy_path.stat().st_mtime, now)

        with self.receipt.open("r", encoding="utf-8") as source_file:
            with dump_path.open("r", encoding="utf-8") as dump_file:
                for line, (source, dump) in enumerate(
                    zip_longest(source_file, dump_file)
                ):
                    with self.subTest(file=self.receipt.name, line=line):
                        self.assertEqual(source.replace(", other", ""), dump)

        with self.products.open("r", encoding="utf-8") as source_file:
            with products_path.open("r", encoding="utf-8") as dump_file:
                for line, (source, dump) in enumerate(
                    zip_longest(source_file, dump_file)
                ):
                    with self.subTest(file=self.products.name, line=line):
                        self.assertEqual(source, dump)

        with self.shops.open("r", encoding="utf-8") as source_file:
            with shops_path.open("r", encoding="utf-8") as dump_file:
                for line, (source, dump) in enumerate(
                    zip_longest(source_file, dump_file)
                ):
                    with self.subTest(file=self.shops.name, line=line):
                        self.assertEqual(source, dump)

        os.utime(shops_path, times=(now, now))
        os.utime(products_path, times=(now, now))
        os.utime(dump_path, times=(now + 1, now + 1))

        command = Dump()
        command.files = ["receipt.yml"]
        command.run()

        # Existing file is not overridden or has its modification date changed.
        self.assertEqual(shops_path.stat().st_mtime, now)
        self.assertEqual(products_path.stat().st_mtime, now)
        self.assertEqual(dump_path.stat().st_mtime, now + 1)
        self.assertEqual(copy_path.stat().st_mtime, now)

        command = Dump()
        command.files = ["2025-02-31-12-34-mia.yml"]
        command.run()

        missing_path = self.path / "samples" / "2025-02-31-12-34-mia.yml"
        self.assertFalse(missing_path.exists())

        products_path.unlink()

        command = Dump()
        command.files = ["samples/products-id.yml"]
        command.run()

        self.assertTrue(products_path.exists())

        command = Dump()
        command.files = ["shops.yml"]
        command.run()

        self.assertTrue(shops_path.exists())

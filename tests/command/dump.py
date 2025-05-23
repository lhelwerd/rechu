"""
Tests of subcommand to export database entries as YAML files.
"""

from datetime import datetime
from itertools import zip_longest
import os
from pathlib import Path
import shutil
from unittest.mock import patch
from sqlalchemy import select
from rechu.command.dump import Dump
from rechu.io.products import ProductsReader
from rechu.io.receipt import ReceiptReader
from rechu.models.product import Product
from rechu.models.receipt import ProductItem
from ..database import DatabaseTestCase

class DumpTest(DatabaseTestCase):
    """
    Test dumping YAML files from the database.
    """

    # Source data paths
    receipt = Path("samples/receipt.yml").resolve()
    products = Path("samples/products-id.yml")

    # Temporary paths
    path = Path("tmp")
    copy = Path("samples/receipt-1.yml")

    def tearDown(self) -> None:
        super().tearDown()
        shutil.rmtree(self.path, ignore_errors=True)
        self.copy.unlink(missing_ok=True)

    @patch.dict('os.environ', {'RECHU_DATA_PATH': 'tmp'})
    def test_run(self) -> None:
        """
        Test executing the command.
        """

        now = datetime.now()

        with self.database as session:
            for product in ProductsReader(self.products).read():
                session.add(product)
            session.add(next(ReceiptReader(self.receipt, updated=now).read()))
            self.copy.symlink_to(self.receipt.name)
            self.assertEqual(self.copy.resolve(), self.receipt)
            session.add(next(ReceiptReader(self.copy, updated=now).read()))

        # Product matching does not affect receipt dump attributes nor order
        with self.database as session:
            item = session.scalars(select(ProductItem)).first()
            if item is None:
                self.fail("Expected product item to be found in database")
            item.product = session.scalars(select(Product)).first()

        command = Dump()
        command.run()

        # Products are written with the same filename pattern.
        products_path = self.path / "samples" / "products-id.yml"

        # The original receipt filename is preferred over the date format.
        dump_path = self.path / "samples" / "receipt.yml"
        copy_path = self.path / "samples" / "receipt-1.yml"

        self.assertTrue(products_path.exists())
        self.assertTrue(dump_path.exists())
        self.assertTrue(copy_path.exists())

        # The timestamps are set to the receipt model updated time.
        self.assertEqual(dump_path.stat().st_mtime, now.timestamp())
        self.assertEqual(copy_path.stat().st_mtime, now.timestamp())

        with self.receipt.open("r", encoding="utf-8") as source_file:
            with dump_path.open("r", encoding="utf-8") as dump_file:
                for (line, (source, dump)) in enumerate(zip_longest(source_file,
                                                                    dump_file)):
                    with self.subTest(file=self.receipt.name, line=line):
                        self.assertEqual(source.replace(", other", ""), dump)

        with self.products.open("r", encoding="utf-8") as source_file:
            with products_path.open("r", encoding="utf-8") as dump_file:
                for (line, (source, dump)) in enumerate(zip_longest(source_file,
                                                                    dump_file)):
                    with self.subTest(file=self.products.name, line=line):
                        self.assertEqual(source, dump)

        os.utime(products_path, times=(now.timestamp(), now.timestamp()))
        os.utime(dump_path, times=(now.timestamp() + 1, now.timestamp() + 1))

        command = Dump()
        command.files = ["receipt.yml"]
        command.run()

        # Existing file is not overridden or has its modification date changed.
        self.assertEqual(products_path.stat().st_mtime, now.timestamp())
        self.assertEqual(dump_path.stat().st_mtime, now.timestamp() + 1)
        self.assertEqual(copy_path.stat().st_mtime, now.timestamp())

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

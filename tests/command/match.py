"""
Tests of subcommand to match entities in the database.
"""

from pathlib import Path
from typing import final

from sqlalchemy import select

from rechu.command.match import Match
from rechu.io.products import ProductsReader
from rechu.io.receipt import ReceiptReader
from rechu.models.product import LabelMatch, Product
from rechu.models.receipt import Receipt

from ..database import DatabaseTestCase


@final
class MatchTest(DatabaseTestCase):
    """
    Test updating entities with references to metadata.
    """

    def test_run(self) -> None:
        """
        Test executing the command.
        """

        with self.database as session:
            products_path = Path("samples/products-id.yml")
            session.add_all(ProductsReader(products_path).read())
            receipt_path = Path("samples/receipt.yml")
            session.add(next(ReceiptReader(receipt_path).read()))

        command = Match()
        command.run()

        with self.database as session:
            receipt = session.scalars(select(Receipt)).first()
            if receipt is None:
                self.fail("Expected receipt to be stored")

            self.assertIsNone(
                receipt.products[0].product,
                f"Unexpected match for {receipt.products[0]!r}",
            )
            self.assertIsNotNone(
                receipt.products[1].product,
                f"Expected match for {receipt.products[1]!r}",
            )
            self.assertIsNone(
                receipt.products[2].product,
                f"Unexpected match for {receipt.products[2]!r}",
            )

            disco = session.scalars(
                select(Product).where(Product.type == "chocolate")
            ).first()
            if disco is None:
                self.fail("Expected product to be stored")
            disco.labels = [LabelMatch(name="other")]
            for product_range in disco.range:
                product_range.labels = [LabelMatch(name="other")]
            _ = session.merge(disco)
            session.add(
                Product(
                    shop="id", labels=[LabelMatch(name="bulk")], type="test"
                )
            )

        command = Match()
        command.run()

        with self.database as session:
            product = session.scalars(
                select(Product).where(Product.type == "test")
            ).first()
            receipt = session.scalars(select(Receipt)).first()
            if product is None or receipt is None:
                self.fail("Expected product and receipt to be stored")

            self.assertIsNotNone(
                receipt.products[1].product,
                f"Expected match for {receipt.products[1]!r}",
            )
            self.assertNotEqual(
                receipt.products[1].product,
                product,
                f"Unexpected change {receipt.products[1]!r}",
            )
            self.assertEqual(
                receipt.products[2].product,
                product,
                f"Expected match for {receipt.products[2]!r}",
            )

        command = Match()
        command.update = True
        command.run()

        with self.database as session:
            product = session.scalars(
                select(Product).where(Product.type == "test")
            ).first()
            receipt = session.scalars(select(Receipt)).first()
            if product is None or receipt is None:
                self.fail("Expected receipt to be stored")

            self.assertEqual(
                receipt.products[1].product,
                product,
                f"Expected change for {receipt.products[1]!r}",
            )
            self.assertEqual(
                receipt.products[2].product,
                product,
                f"Expected match for {receipt.products[2]!r}",
            )

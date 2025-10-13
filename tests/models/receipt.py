"""
Tests for receipt data models.
"""

from datetime import datetime
from pathlib import Path
from typing import final
import unittest
from sqlalchemy import select
from rechu.io.receipt import ReceiptReader
from rechu.models.base import Price, Quantity
from rechu.models.product import Product
from rechu.models.receipt import Receipt, ProductItem, Discount
from rechu.models.shop import Shop, DiscountIndicator
from ..database import DatabaseTestCase


@final
class ReceiptTest(unittest.TestCase):
    """
    Tests for receipt model.
    """

    def test_repr(self) -> None:
        """
        Test the string representation of the model.
        """

        updated = datetime(2024, 11, 1, 12, 34, 0)
        self.assertEqual(
            repr(
                Receipt(
                    filename="file",
                    updated=updated,
                    date=updated.date(),
                    shop="id",
                )
            ),
            "Receipt(date='2024-11-01', shop='id')",
        )

    def test_total_price(self) -> None:
        """
        Test retrieving the total cost of a receipt after discounts.
        """

        receipt = next(ReceiptReader(Path("samples/receipt.yml")).read())
        self.assertEqual(
            receipt.total_price,
            Price("0.99")
            + Price("5.00")
            + Price("7.50")
            + Price("8.00")
            + Price("2.50")
            + Price("0.89")
            - Price("2.00")
            - Price("0.22")
            - Price("0.02")
            - Price("0.20"),
        )

    def test_total_discount(self) -> None:
        """
        Test the total discount of a receipt.
        """

        receipt = next(ReceiptReader(Path("samples/receipt.yml")).read())
        self.assertEqual(
            receipt.total_discount,
            Price("0")
            - Price("2.00")
            - Price("0.22")
            - Price("0.02")
            - Price("0.20"),
        )


@final
class ProductItemTest(DatabaseTestCase):
    """
    Tests for receipt product item model.
    """

    def test_discount_indicators(self) -> None:
        """
        Test retrieving discrete portions of the discount indicator.
        """

        self.assertEqual(
            ProductItem(
                quantity=Quantity("1"),
                label="label",
                price=Price("0.99"),
                discount_indicator=None,
                position=0,
            ).discount_indicators,
            [],
        )

        shop = Shop(
            key="id",
            discount_indicators=[
                DiscountIndicator(pattern="b"),
                DiscountIndicator(pattern=r"\d+%"),
            ],
        )
        receipt = Receipt(filename="file", shop_meta=shop)
        product = ProductItem(
            quantity=Quantity("2"),
            label="bulk",
            price=Price("5.00"),
            discount_indicator="50%",
            position=0,
            amount=2,
            unit=None,
            receipt=receipt,
        )
        self.assertEqual(product.discount_indicators, ["50%"])

        product.discount_indicator = "b25%ex"
        self.assertEqual(product.discount_indicators, ["b", "25%", "ex"])

    def test_repr(self) -> None:
        """
        Test the string representation of the model.
        """

        self.assertEqual(
            repr(
                ProductItem(
                    quantity=Quantity("1"),
                    label="label",
                    price=Price("0.99"),
                    discount_indicator=None,
                    position=0,
                )
            ),
            (
                "ProductItem(receipt=None, quantity='1', "
                "label='label', price=0.99, discount_indicator=None, "
                "product=None)"
            ),
        )

        updated = datetime(2024, 11, 1, 12, 34, 0)
        receipt = Receipt(
            filename="file", updated=updated, date=updated.date(), shop="id"
        )
        product = ProductItem(
            quantity=Quantity("2"),
            label="bulk",
            price=Price("5.00"),
            discount_indicator="bonus",
            position=0,
            amount=2,
            unit=None,
        )
        receipt.products = [product]
        product.product = Product(shop="id", sku="1234")
        with self.database as session:
            session.add(receipt)
            session.flush()
            self.assertEqual(
                repr(product),
                (
                    "ProductItem(receipt='file', quantity='2', "
                    "label='bulk', price=5.00, "
                    "discount_indicator='bonus', product=1)"
                ),
            )
        with self.database as session:
            self.assertEqual(
                repr(session.scalars(select(ProductItem)).first()),
                (
                    "ProductItem(receipt='file', quantity='2', "
                    "label='bulk', price=5.00, "
                    "discount_indicator='bonus', product=1)"
                ),
            )


class DiscountTest(DatabaseTestCase):
    """
    Tests for receipt discount model.
    """

    def test_repr(self) -> None:
        """
        Test the string representation of the model.
        """

        updated = datetime(2024, 11, 1, 12, 34, 0)
        receipt = Receipt(
            filename="file", updated=updated, date=updated.date(), shop="id"
        )
        product = ProductItem(
            quantity=Quantity("2"),
            label="bulk",
            price=Price("5.00"),
            discount_indicator="bonus",
            position=0,
            amount=2,
            unit=None,
        )
        discount = Discount(
            label="disco",
            price_decrease=Price("-2.00"),
            items=[product],
            position=0,
        )
        self.assertEqual(
            repr(discount),
            (
                "Discount(receipt=None, label='disco', "
                "price_decrease=-2.00, items=['bulk'])"
            ),
        )

        receipt.products = [product]
        receipt.discounts = [discount]
        with self.database as session:
            session.add(receipt)
            session.flush()
            self.assertEqual(
                repr(discount),
                (
                    "Discount(receipt='file', label='disco', "
                    "price_decrease=-2.00, items=['bulk'])"
                ),
            )
        with self.database as session:
            self.assertEqual(
                repr(session.scalars(select(Discount)).first()),
                (
                    "Discount(receipt='file', label='disco', "
                    "price_decrease=-2.00, items=['bulk'])"
                ),
            )

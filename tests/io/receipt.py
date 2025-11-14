"""
Tests for receipt file handling.
"""

import unittest
from datetime import date, datetime
from io import StringIO
from itertools import zip_longest
from pathlib import Path
from typing import cast, final

import yaml
from typing_extensions import TypedDict, override

from rechu.io.receipt import ReceiptReader, ReceiptWriter
from rechu.models.base import Price, Quantity
from rechu.models.receipt import Discount, ProductItem, Receipt


class _ProductData(TypedDict, total=True):
    quantity: Quantity
    label: str
    price: Price
    discount_indicator: str | None


class _DiscountData(TypedDict, total=True):
    label: str
    price_decrease: Price
    items: list[int]


class _ReceiptData(TypedDict, total=True):
    products: list[_ProductData]
    discounts: list[_DiscountData]


class _Receipt(TypedDict, total=True):
    date: date
    shop: str
    products: list[_ProductData]
    bonus: list[list[str | Price]]


expected: _ReceiptData = {
    "products": [
        {
            "quantity": Quantity("1"),
            "label": "label",
            "price": Price("0.99"),
            "discount_indicator": None,
        },
        {
            "quantity": Quantity("2"),
            "label": "bulk",
            "price": Price("5.00"),
            "discount_indicator": "bonus",
        },
        {
            "quantity": Quantity("3"),
            "label": "bulk",
            "price": Price("7.50"),
            "discount_indicator": None,
        },
        {
            "quantity": Quantity("4"),
            "label": "bulk",
            "price": Price("8.00"),
            "discount_indicator": "bonus",
        },
        {
            "quantity": Quantity("0.750kg"),
            "label": "weigh",
            "price": Price("2.50"),
            "discount_indicator": None,
        },
        {
            "quantity": Quantity("1"),
            "label": "due",
            "price": Price("0.89"),
            "discount_indicator": "25%",
        },
    ],
    "discounts": [
        {"label": "disco", "price_decrease": Price("-2.00"), "items": [1, 3]},
        {"label": "over", "price_decrease": Price("-0.22"), "items": [5]},
        {"label": "none", "price_decrease": Price("-0.02"), "items": []},
        {"label": "missing", "price_decrease": Price("-0.20"), "items": []},
    ],
}


@final
class ReceiptReaderTest(unittest.TestCase):
    """
    Tests for receipt file reader.
    """

    def test_parse(self) -> None:
        """
        Test parsing an open file and yielding receipt models from it.
        """

        path = Path("samples/receipt.yml")
        reader = ReceiptReader(path)
        with path.open("r", encoding="utf-8") as file:
            generator = reader.parse(file)
            receipt = next(generator)
            self.assertEqual(receipt.filename, "receipt.yml")
            self.assertEqual(receipt.date, date(2024, 11, 1))
            self.assertEqual(receipt.shop, "id")
            self.assertEqual(len(receipt.products), len(expected["products"]))
            for index, product in enumerate(expected["products"]):
                with self.subTest(product=index):
                    self.assertEqual(
                        receipt.products[index].quantity, product["quantity"]
                    )
                    self.assertEqual(
                        receipt.products[index].label, product["label"]
                    )
                    self.assertEqual(
                        receipt.products[index].price, product["price"]
                    )
                    self.assertEqual(
                        receipt.products[index].discount_indicator,
                        product["discount_indicator"],
                    )
                    self.assertEqual(receipt.products[index].position, index)
                    self.assertEqual(
                        receipt.products[index].amount,
                        product["quantity"].amount,
                    )
                    self.assertEqual(
                        receipt.products[index].unit, product["quantity"].unit
                    )
            self.assertEqual(len(receipt.discounts), len(expected["discounts"]))
            for index, discount in enumerate(expected["discounts"]):
                with self.subTest(discount=index):
                    self.assertEqual(
                        receipt.discounts[index].label, discount["label"]
                    )
                    self.assertEqual(
                        receipt.discounts[index].price_decrease,
                        discount["price_decrease"],
                    )
                    items = discount["items"]
                    self.assertEqual(
                        len(receipt.discounts[index].items), len(items)
                    )
                    for number, item in zip(
                        items, receipt.discounts[index].items, strict=True
                    ):
                        with self.subTest(discountItem=number):
                            self.assertEqual(receipt.products[number], item)
                            self.assertIn(
                                receipt.discounts[index], item.discounts
                            )

                    self.assertEqual(receipt.discounts[index].position, index)

        with self.assertRaises(StopIteration):
            self.assertIsNone(next(generator))

    def test_parse_invalid(self) -> None:
        """
        Test parsing an open file and raising type errors from it.
        """

        tests = [
            ("number.yml", "File '.*' does not contain .*dict"),
            ("flow.yml", "YAML failure in file '.*' while parsing a flow node"),
            ("shop.yml", "Missing field in file '.*': 'shop'"),
            ("product_fields.yml", "Product item has too few elements: 2"),
            ("price.yml", "Price '{}' could not be converted"),
            ("discount_fields.yml", "Discount has too few elements: 1"),
        ]

        for filename, pattern in tests:
            with self.subTest(filename=filename):
                path = Path("samples/invalid-receipt") / filename
                reader = ReceiptReader(path)
                with path.open("r", encoding="utf-8") as file:
                    with self.assertRaisesRegex(TypeError, pattern):
                        self.assertIsNone(next(reader.parse(file)))


@final
class ReceiptWriterTest(unittest.TestCase):
    """
    Tests for receipt file writer.
    """

    @override
    def setUp(self) -> None:
        updated = datetime(2024, 11, 1, 12, 34, 0)
        self.model = Receipt(
            filename="file", updated=updated, date=updated.date(), shop="id"
        )
        self.model.products = [
            ProductItem(
                quantity=Quantity("1"),
                label="label",
                price=Price("0.99"),
                discount_indicator=None,
            ),
            ProductItem(
                quantity=Quantity("2"),
                label="bulk",
                price=Price("5.00"),
                discount_indicator="bonus",
            ),
            ProductItem(
                quantity=Quantity("3"),
                label="bulk",
                price=Price("7.50"),
                discount_indicator=None,
            ),
            ProductItem(
                quantity=Quantity("4"),
                label="bulk",
                price=Price("8.00"),
                discount_indicator="bonus",
            ),
            ProductItem(
                quantity=Quantity("0.750kg"),
                label="weigh",
                price=Price("2.50"),
                discount_indicator=None,
            ),
            ProductItem(
                quantity=Quantity("1"),
                label="due",
                price=Price("0.89"),
                discount_indicator="25%",
            ),
        ]
        self.model.discounts = [
            Discount(
                label="disco",
                price_decrease=Price("-2.00"),
                items=[self.model.products[1], self.model.products[3]],
            ),
            Discount(
                label="over",
                price_decrease=Price("-0.22"),
                items=[self.model.products[5]],
            ),
            Discount(label="none", price_decrease=Price("-0.02"), items=[]),
            Discount(label="missing", price_decrease=Price("-0.20"), items=[]),
        ]

    @override
    def tearDown(self) -> None:
        Path("samples/new_receipt.yml").unlink(missing_ok=True)

    def test_serialize(self) -> None:
        """
        Test writing a serialized variant of a model to an open file.
        """

        path = Path("samples/receipt.yml")
        with self.assertRaisesRegex(
            TypeError, "Can only write exactly one receipt.*"
        ):
            writer = ReceiptWriter(path, [])
        writer = ReceiptWriter(path, (self.model,))
        file = StringIO()
        writer.serialize(file)

        _ = file.seek(0)
        lines = file.readlines()
        actual = cast(_Receipt, yaml.safe_load("\n".join(lines)))

        self.assertEqual(actual.get("date"), date(2024, 11, 1))
        self.assertEqual(actual.get("shop"), "id")
        self.assertEqual(len(actual["products"]), len(expected["products"]))
        for index, product in enumerate(expected["products"]):
            with self.subTest(product=index):
                quantity = (
                    str(product["quantity"])
                    if product["quantity"].unit
                    else int(product["quantity"])
                )
                if product["discount_indicator"] is None:
                    self.assertEqual(
                        actual["products"][index],
                        [quantity, product["label"], float(product["price"])],
                    )
                else:
                    self.assertEqual(
                        actual["products"][index],
                        [
                            quantity,
                            product["label"],
                            float(product["price"]),
                            product["discount_indicator"],
                        ],
                    )
        self.assertEqual(len(actual["bonus"]), len(expected["discounts"]))
        for index, discount in enumerate(expected["discounts"]):
            with self.subTest(discount=index):
                self.assertEqual(actual["bonus"][index][0], discount["label"])
                self.assertEqual(
                    actual["bonus"][index][1], float(discount["price_decrease"])
                )
                items = discount["items"]
                self.assertEqual(
                    actual["bonus"][index][2:],
                    [
                        str(expected["products"][item]["label"])
                        for item in items
                    ],
                )

        # Serialization should look the same way, including price precisions.
        with path.open("r", encoding="utf-8") as original_file:
            for line, (original, new) in enumerate(
                zip_longest(original_file, lines)
            ):
                with self.subTest(line=line):
                    if original is None:
                        self.fail(f"Superfluous line {new}")
                    self.assertEqual(original.replace(", other", ""), new)

    def test_write(self) -> None:
        """
        Test writing a model to a path.
        """

        path = Path("samples/new_receipt.yml")
        writer = ReceiptWriter(path, (self.model,))
        writer.write()
        self.assertTrue(path.exists())
        self.assertEqual(path.stat().st_mtime, self.model.updated.timestamp())

        now = datetime.now()
        writer = ReceiptWriter(path, (self.model,), updated=now)
        writer.write()
        self.assertEqual(path.stat().st_mtime, now.timestamp())

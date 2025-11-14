"""
Tests for product metadata model.
"""

from itertools import zip_longest
from typing import final

from typing_extensions import override

from rechu.models.base import Price, Quantity
from rechu.models.product import DiscountMatch, LabelMatch, PriceMatch, Product

from ..database import DatabaseTestCase


@final
class ProductTest(DatabaseTestCase):
    """
    Tests for product model.
    """

    @override
    def setUp(self) -> None:
        super().setUp()

        # These may be changed during test so no class members
        self.product = Product(
            shop="id",
            labels=[LabelMatch(name="first")],
            prices=[
                PriceMatch(value=Price("0.01")),
                PriceMatch(value=Price("0.03")),
            ],
            discounts=[DiscountMatch(label="one")],
            brand="abc",
            description="def",
            category="foo",
            type="bar",
            portions=12,
            range=[Product(shop="id")],
        )
        self.other = Product(
            id=3,
            shop="id",
            labels=[LabelMatch(name="first"), LabelMatch(name="second")],
            discounts=[DiscountMatch(label="one"), DiscountMatch(label="2")],
            weight=Quantity("750g"),
            volume=Quantity("1l"),
            alcohol="2.0%",
            sku="1234",
            gtin=1234567890123,
            range=[Product(shop="id", sku="5x"), Product(shop="id", sku="5y")],
        )

    def test_clear(self) -> None:
        """
        Test removing all properties of the product.
        """

        self.product.clear()
        self.assertEqual(self.product.shop, "id")
        self.assertEqual(self.product.labels, [])
        self.assertEqual(self.product.prices, [])
        self.assertEqual(self.product.discounts, [])
        self.assertEqual(self.product.range, [])
        self.assertIsNone(self.product.brand)

        self.other.range[1].clear()
        self.assertEqual(self.other.range[1].shop, "id")
        self.assertEqual(len(self.other.range[1].labels), 2)
        self.assertEqual(self.other.range[1].labels[0].name, "first")
        self.assertEqual(self.other.range[1].labels[1].name, "second")
        self.assertEqual(self.other.range[1].prices, [])
        self.assertEqual(len(self.other.range[1].discounts), 2)
        self.assertEqual(self.other.range[1].discounts[0].label, "one")
        self.assertEqual(self.other.range[1].discounts[1].label, "2")
        self.assertEqual(self.other.range[1].alcohol, "2.0%")
        self.assertEqual(self.other.range[1].generic, self.other)

    def test_replace(self) -> None:
        """
        Test replacing all properties with those defined in the new product.
        """

        self.assertTrue(
            self.product.replace(Product(shop="id", gtin=4321987654321))
        )
        self.assertEqual(self.product.shop, "id")
        self.assertEqual(self.product.labels, [])
        self.assertEqual(self.product.prices, [])
        self.assertEqual(self.product.discounts, [])
        self.assertEqual(self.product.range, [])
        self.assertIsNone(self.product.brand)
        self.assertEqual(self.product.gtin, 4321987654321)

        self.assertTrue(
            self.other.range[1].replace(Product(shop="id", sku="5z"))
        )
        self.assertEqual(self.other.range[1].shop, "id")
        self.assertEqual(len(self.other.range[1].labels), 2)
        self.assertEqual(self.other.range[1].labels[0].name, "first")
        self.assertEqual(self.other.range[1].labels[1].name, "second")
        self.assertEqual(self.other.range[1].prices, [])
        self.assertEqual(len(self.other.range[1].discounts), 2)
        self.assertEqual(self.other.range[1].discounts[0].label, "one")
        self.assertEqual(self.other.range[1].discounts[1].label, "2")
        self.assertEqual(self.other.range[1].alcohol, "2.0%")
        self.assertEqual(self.other.range[1].sku, "5z")
        self.assertEqual(self.other.range[1].generic, self.other)

        # Replacing matchers override generic matchers.
        new_range = Product(
            shop="id",
            labels=[LabelMatch(name="init")],
            prices=[PriceMatch(value=Price("1.00"))],
            discounts=[DiscountMatch(label="tri")],
        )
        self.assertTrue(self.other.range[1].replace(new_range))
        self.assertEqual(len(self.other.range[1].labels), 1)
        self.assertEqual(self.other.range[1].labels[0].name, "init")
        self.assertEqual(len(self.other.range[1].prices), 1)
        self.assertEqual(self.other.range[1].prices[0].value, Price("1.00"))
        self.assertEqual(len(self.other.range[1].discounts), 1)
        self.assertEqual(self.other.range[1].discounts[0].label, "tri")

    def test_copy(self) -> None:
        """
        Test copying the product.
        """

        copy = self.product.copy()
        self.assertIsNot(self.product, copy)
        self.assertEqual(self.product.shop, copy.shop)
        self.assertEqual(
            [label.name for label in self.product.labels],
            [label.name for label in copy.labels],
        )
        self.assertEqual(len(self.product.range), len(copy.range))
        self.assertFalse(self.product.merge(copy))

    def _check_merge(self) -> None:
        # ID is updated but shop is not
        self.assertEqual(self.product.id, 3)
        self.assertEqual(self.product.shop, "id")

        self.assertEqual(len(self.product.labels), 2)
        self.assertEqual(self.product.labels[0].name, "first")
        self.assertEqual(self.product.labels[1].name, "second")

        self.assertEqual(len(self.product.prices), 2)

        self.assertEqual(len(self.product.discounts), 2)
        self.assertEqual(self.product.discounts[0].label, "one")
        self.assertEqual(self.product.discounts[1].label, "2")

        self.assertEqual(self.product.brand, "abc")
        self.assertEqual(self.product.description, "def")
        self.assertEqual(self.product.category, "foo")
        self.assertEqual(self.product.type, "bar")
        self.assertEqual(self.product.portions, 12)

        self.assertEqual(self.product.weight, Quantity("750g"))
        self.assertEqual(self.product.volume, Quantity("1l"))
        self.assertEqual(self.product.alcohol, "2.0%")
        self.assertEqual(self.product.sku, "1234")
        self.assertEqual(self.product.gtin, 1234567890123)

        self.assertEqual(len(self.product.range), 2)
        self.assertEqual(self.product.range[0].shop, "id")
        self.assertEqual(self.product.range[0].sku, "5x")
        self.assertEqual(self.product.range[1].shop, "id")
        self.assertEqual(self.product.range[1].sku, "5y")

    def test_check_merge(self) -> None:
        """
        Check if another product is compatible with merging.
        """

        # No exception raised
        self.product.check_merge(self.other)

        with self.assertRaisesRegex(ValueError, ".*shop.*"):
            self.product.check_merge(Product(shop="other"))

        prices_indicators = [
            PriceMatch(value=Price("0.98"), indicator="minimum"),
            PriceMatch(value=Price("0.50"), indicator="2024"),
        ]
        indicator = Product(shop="id", prices=prices_indicators)
        with self.assertRaisesRegex(ValueError, ".*indicators.*"):
            self.product.check_merge(indicator)

    def test_merge(self) -> None:
        """
        Test merging attributes of another product.
        """

        self.assertTrue(self.product.merge(self.other))

        self._check_merge()

        self.assertFalse(self.product.merge(self.other))

        less = Product(shop="id")
        more = Product(shop="id", id=3)
        self.assertFalse(less.merge(more))
        self.assertEqual(less.id, 3)

        with self.assertRaisesRegex(ValueError, ".*shop.*"):
            self.assertFalse(self.product.merge(Product(shop="other")))

        prices_indicators = [
            PriceMatch(value=Price("0.98"), indicator="minimum"),
            PriceMatch(value=Price("0.50"), indicator="2024"),
        ]
        indicator = Product(shop="id", prices=prices_indicators)
        with self.assertRaisesRegex(ValueError, ".*indicators.*"):
            self.assertFalse(self.product.merge(indicator))

        tests: tuple[Product, ...] = (self.product, indicator)
        new_price_tests: tuple[list[PriceMatch], ...] = (
            [PriceMatch(value=Price("0.01")), PriceMatch(value=Price("0.02"))],
            [
                PriceMatch(value=Price("0.98"), indicator="minimum"),
                PriceMatch(value=Price("1.99"), indicator="maximum"),
                PriceMatch(value=Price("0.50"), indicator="2024"),
                PriceMatch(value=Price("0.75"), indicator="2025"),
            ],
        )
        expected_price_tests: tuple[list[tuple[str, str | None]], ...] = (
            [("0.01", None), ("0.03", None), ("0.02", None)],
            [
                ("0.98", "minimum"),
                ("0.50", "2024"),
                ("1.99", "maximum"),
                ("0.75", "2025"),
            ],
        )
        for test, new, expected_prices in zip(
            tests, new_price_tests, expected_price_tests, strict=True
        ):
            self.assertTrue(test.merge(Product(shop="id", prices=new)))
            for i, (price, expected) in enumerate(
                zip_longest(test.prices, expected_prices)
            ):
                with self.subTest(product=test, index=i):
                    if price is None:
                        self.fail("Not enough prices in merged product")
                    if expected is None:
                        self.fail("Too many prices in merged product")
                    self.assertEqual(price.value, Price(expected[0]))
                    self.assertEqual(price.indicator, expected[1])

    def test_merge_no_replace(self) -> None:
        """
        Test merging attributes of another product without changing simple
        property fields that already have values.
        """

        self.assertTrue(self.product.merge(self.other, replace=False))

        self._check_merge()

        self.assertFalse(self.product.merge(self.other, replace=False))

        self.assertFalse(
            self.product.merge(
                Product(
                    shop="id", brand="ghi", weight=Quantity("500g"), sku="5678"
                ),
                replace=False,
            )
        )
        self._check_merge()

        self.assertFalse(
            self.product.merge(
                Product(shop="id", range=[Product(shop="id", sku="5z")]),
                replace=False,
            )
        )

        self._check_merge()

    def test_repr(self) -> None:
        """
        Test the string representation of the model.
        """

        product = Product(
            shop="id",
            brand="abc",
            description="def",
            category="foo",
            type="bar",
            portions=12,
            weight=Quantity("750g"),
            volume=Quantity("1l"),
            alcohol="2.0%",
            sku="1234",
            gtin=1234567890123,
        )
        self.assertEqual(
            repr(product),
            (
                "Product(id=None, shop='id', labels=[], prices=[], "
                "discounts=[], brand='abc', description='def', "
                "category='foo', type='bar', portions=12, "
                "weight='750g', volume='1l', alcohol='2.0%', "
                "sku='1234', gtin=1234567890123, range=[])"
            ),
        )
        product.labels = [LabelMatch(product=product, name="label")]
        product.prices = [
            PriceMatch(
                product=product, value=Price("1.23"), indicator="minimum"
            ),
            PriceMatch(
                product=product, value=Price("7.89"), indicator="maximum"
            ),
        ]
        product.discounts = [DiscountMatch(product=product, label="disco")]
        product.type = None
        product.volume = None
        product.range = [Product(shop="id", sku="5")]
        with self.database as session:
            session.add(product)
            session.flush()
            self.assertEqual(
                repr(product),
                (
                    "Product(id=1, shop='id', labels=['label'], "
                    "prices=[('minimum', 1.23), ('maximum', 7.89)], "
                    "discounts=['disco'], brand='abc', "
                    "description='def', category='foo', type=None, "
                    "portions=12, weight='750g', volume=None, "
                    "alcohol='2.0%', sku='1234', gtin=1234567890123, "
                    "range=[Product(id=2, shop='id', labels=[], "
                    "prices=[], discounts=[], brand=None, "
                    "description=None, category=None, type=None, "
                    "portions=None, weight=None, volume=None, "
                    "alcohol=None, sku='5', gtin=None)])"
                ),
            )

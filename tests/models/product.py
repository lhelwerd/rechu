"""
Tests for product metadata model.
"""

import unittest
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
            labels=[
                LabelMatch(id=61, name="first"),
                LabelMatch(id=62, name="second"),
            ],
            discounts=[
                DiscountMatch(id=71, label="one"),
                DiscountMatch(id=72, label="2"),
            ],
            weight=Quantity("750g"),
            volume=Quantity("1l"),
            alcohol="2.0%",
            sku="1234",
            gtin=1234567890123,
            range=[
                Product(id=4, shop="id", sku="5x", generic_id=3),
                Product(id=5, shop="id", sku="5y", generic_id=3),
            ],
        )

    def test_equals(self) -> None:
        """
        Test determining whether the product has the exact same fields as the
        other product.
        """

        self.assertFalse(self.product.equals(self.other))
        same = Product(
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
        self.assertTrue(self.other.equals(same))
        self.assertTrue(self.other.range[1].equals(same.range[1]))

        empty = Product(shop="id")
        self.assertFalse(
            Product(shop="id", labels=[LabelMatch(name="one")]).equals(empty)
        )
        self.assertFalse(
            Product(shop="id", labels=[LabelMatch(name="one")]).equals(
                Product(shop="id", labels=[LabelMatch(name="two")])
            )
        )
        self.assertFalse(
            Product(shop="id", prices=[PriceMatch(value=Price("0.12"))]).equals(
                empty
            )
        )
        self.assertFalse(
            Product(shop="id", prices=[PriceMatch(value=Price("0.12"))]).equals(
                Product(shop="id", prices=[PriceMatch(value=Price("1.23"))])
            )
        )
        self.assertFalse(
            Product(shop="id", discounts=[DiscountMatch(label="one")]).equals(
                empty
            )
        )
        self.assertFalse(
            Product(shop="id", discounts=[DiscountMatch(label="one")]).equals(
                Product(shop="id", discounts=[DiscountMatch(label="two")])
            )
        )

        self.assertFalse(Product(shop="id", range=[empty]).equals(empty))
        self.assertFalse(
            Product(shop="id", range=[empty]).equals(
                Product(
                    shop="id", range=[Product(shop="id", description="bar")]
                )
            )
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

        # No exception raised for indicdator/indicatorless merge
        prices_indicators = [
            PriceMatch(value=Price("0.98"), indicator="minimum"),
            PriceMatch(value=Price("0.50"), indicator="2024"),
        ]
        indicator = Product(shop="id", prices=prices_indicators)
        self.product.check_merge(indicator)

    def test_merge(self) -> None:
        """
        Test merging attributes of another product.
        """

        self.assertTrue(self.product.merge(self.other))

        self._check_merge()

        self.assertFalse(self.product.merge(self.other))

        id_less = Product(shop="id")
        id_more = Product(shop="id", id=3)
        self.assertFalse(id_less.merge(id_more))
        self.assertEqual(id_less.id, 3)

        brand_less = Product(shop="id")
        brand_more = Product(shop="id", brand="foo")
        self.assertFalse(brand_more.merge(brand_less))
        self.assertEqual(brand_more.brand, "foo")

        with self.assertRaisesRegex(ValueError, ".*shop.*"):
            self.assertFalse(self.product.merge(Product(shop="other")))

    def test_merge_price_match(self) -> None:
        """
        Test merging attributes of another product with price matchers.
        """

        prices_indicators = [
            PriceMatch(value=Price("0.98"), indicator="minimum"),
            PriceMatch(value=Price("0.50"), indicator="2024"),
            PriceMatch(value=Price("1.50"), indicator="2026"),
        ]
        indicator = Product(shop="id", prices=prices_indicators)

        tests: tuple[Product, ...] = (
            self.product.copy(),
            indicator.copy(),
            self.product.copy(),
            indicator.copy(),
            Product(
                shop="id",
                prices=[PriceMatch(value=Price("2.00"), indicator="maximum")],
            ),
            Product(
                shop="id",
                prices=[
                    PriceMatch(value=Price("2.99"), indicator="minimum"),
                    PriceMatch(value=Price("2.99"), indicator="maximum"),
                ],
            ),
        )
        new_price_tests: tuple[list[PriceMatch], ...] = (
            [PriceMatch(value=Price("0.01")), PriceMatch(value=Price("0.02"))],
            [
                PriceMatch(value=Price("0.97"), indicator="minimum"),
                PriceMatch(value=Price("1.98"), indicator="maximum"),
                PriceMatch(value=Price("0.50"), indicator="2024"),
                PriceMatch(value=Price("0.75"), indicator="2025"),
                PriceMatch(value=Price("1.25"), indicator="2026"),
            ],
            [PriceMatch(value=Price("0.04"), indicator="2026")],
            [PriceMatch(value=Price("0.48"), indicator=None)],
            [PriceMatch(value=Price("2.50"), indicator=None)],
            [PriceMatch(value=Price("2.75"), indicator="minimum")],
        )
        expected_price_tests: tuple[list[tuple[str, str | None]], ...] = (
            [("0.01", None), ("0.03", None), ("0.02", None)],
            [
                ("0.97", "minimum"),
                ("0.50", "2024"),
                ("1.25", "2026"),
                ("1.98", "maximum"),
                ("0.75", "2025"),
            ],
            [
                ("0.01", "minimum"),
                ("0.03", "maximum"),
                ("0.04", "2026"),
            ],
            [
                ("0.48", "minimum"),
                ("0.50", "2024"),
                ("1.50", "2026"),
            ],
            [("2.50", "maximum")],
            [("2.75", "minimum"), ("2.99", "maximum")],
        )
        for t, (test, new, expected_prices) in enumerate(
            zip(tests, new_price_tests, expected_price_tests, strict=True)
        ):
            self.assertTrue(test.merge(Product(shop="id", prices=new)))
            for i, (price, expected) in enumerate(
                zip_longest(test.prices, expected_prices)
            ):
                with self.subTest(product=test, test=t, index=i):
                    if price is None:
                        self.fail("Not enough prices in merged product")
                    if expected is None:
                        self.fail("Too many prices in merged product")
                    self.assertEqual(
                        (str(price.value), price.indicator),
                        (expected[0], expected[1]),
                    )

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

    def test_merge_ids(self) -> None:
        """
        Test copying over primary key identifiers.
        """

        self.assertTrue(self.product.merge_ids(self.other))
        self.assertEqual(self.product.id, 3)
        self.assertEqual(self.product.labels[0].id, 61)
        self.assertIsNone(self.product.prices[0].id)
        self.assertIsNone(self.product.prices[1].id)
        self.assertEqual(self.product.discounts[0].id, 71)
        self.assertEqual(self.product.range[0].id, 4)
        self.assertEqual(self.product.range[0].generic_id, 3)

        self.assertFalse(self.product.merge_ids(self.other))

        price = Product(
            id=333,
            shop="id",
            prices=[
                PriceMatch(id=80, value=Price("0.03"), indicator="2026"),
                PriceMatch(id=81, value=Price("0.01")),
            ],
        )
        self.assertTrue(self.product.merge_ids(price))
        self.assertEqual(self.product.id, 333)
        self.assertEqual(self.product.prices[0].id, 81)

    def test_has_patterns(self) -> None:
        """
        Test determining whether any of the matcgers have regular expressions.
        """

        self.assertFalse(self.product.has_patterns)
        self.assertFalse(self.other.has_patterns)

        label = Product(
            shop="id",
            labels=[LabelMatch(name="^first"), LabelMatch(name="second")],
        )
        self.assertTrue(label.has_patterns)
        discount = Product(
            shop="id",
            labels=[LabelMatch(name="first"), LabelMatch(name="second")],
            discounts=[DiscountMatch(label="^.ne+"), DiscountMatch(label="2")],
        )
        self.assertTrue(discount.has_patterns)

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

    def test_origin(self) -> None:
        """
        Test the origin indicator.
        """

        self.assertEqual(self.product.origin, "external")
        with self.database as session:
            session.add(self.product)
            session.flush()
        self.assertEqual(self.product.origin, "db")


class LabelMatchTest(unittest.TestCase):
    """
    Tests for label model of a product matching string.
    """

    label: LabelMatch = LabelMatch(name="foo")

    def test_equals(self) -> None:
        """
        Check if the label matcher is the same as another.
        """

        self.assertTrue(self.label.equals(LabelMatch(id=123, name="foo")))
        self.assertFalse(self.label.equals(LabelMatch(name="bar")))

    def test_set_is_pattern(self) -> None:
        """
        Test determining if the label name is a regular expression matcher.
        """

        self.assertEqual(self.label.set_is_pattern("name", "foo"), "foo")
        self.assertFalse(self.label.is_pattern)
        self.assertEqual(self.label.set_is_pattern("name", "^foo"), "^foo")
        self.assertTrue(self.label.is_pattern)

        self.assertTrue(LabelMatch(name="^baz").is_pattern)

        with self.assertRaisesRegex(KeyError, "Expected name input"):
            self.assertNotEqual(
                self.label.set_is_pattern("product", "bar"), "bar"
            )

    def test_repr(self) -> None:
        """
        Test the string representation of the model.
        """

        self.assertEqual(repr(self.label), "'foo'")


class PriceMatchTest(unittest.TestCase):
    """
    Tests for price model of a product matching value.
    """

    price: PriceMatch = PriceMatch(value=Price("0.12"), indicator="minimum")

    def test_equals(self) -> None:
        """
        Check if the label matcher is the same as another.
        """

        self.assertTrue(
            self.price.equals(
                PriceMatch(id=123, value=Price("0.12"), indicator="minimum")
            )
        )
        self.assertFalse(self.price.equals(PriceMatch(value=Price("0.12"))))
        self.assertFalse(
            self.price.equals(
                PriceMatch(value=Price("1.23"), indicator="minimum")
            )
        )

    def test_repr(self) -> None:
        """
        Test the string representation of the model.
        """

        self.assertEqual(repr(self.price), "('minimum', 0.12)")


class DiscountMatchTest(unittest.TestCase):
    """
    Tests for discount label model of a product matching string.
    """

    discount: DiscountMatch = DiscountMatch(label="foo")

    def test_equals(self) -> None:
        """
        Test checking if the discount matcher is the same as another.
        """

        self.assertTrue(
            self.discount.equals(DiscountMatch(id=123, label="foo"))
        )
        self.assertFalse(self.discount.equals(DiscountMatch(label="bar")))

    def test_set_is_pattern(self) -> None:
        """
        Test determining if the discount label is a regular expression matcher.
        """

        self.assertEqual(self.discount.set_is_pattern("label", "foo"), "foo")
        self.assertFalse(self.discount.is_pattern)
        self.assertEqual(self.discount.set_is_pattern("label", "^foo"), "^foo")
        self.assertTrue(self.discount.is_pattern)

        self.assertTrue(DiscountMatch(label="^zzz").is_pattern)

        with self.assertRaisesRegex(KeyError, "Expected label input"):
            self.assertNotEqual(
                self.discount.set_is_pattern("product", "bar"), "bar"
            )

    def test_repr(self) -> None:
        """
        Test the string representation of the model.
        """

        self.assertEqual(repr(self.discount), "'foo'")

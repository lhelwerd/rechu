"""
Tests for product metadata matcher.
"""

from copy import copy
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import final
from unittest.mock import MagicMock

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from rechu.io.products import ProductsReader
from rechu.io.receipt import ReceiptReader
from rechu.matcher.product import MapKey, ProductMatcher
from rechu.models.base import Price, Quantity
from rechu.models.product import DiscountMatch, LabelMatch, PriceMatch, Product
from rechu.models.receipt import Discount, ProductItem, Receipt

from ..database import DatabaseTestCase

PriceTest = tuple[list[PriceMatch], Price, Quantity]
PriceTests = tuple[PriceTest, ...]


@final
class ProductMatcherTest(DatabaseTestCase):
    """
    Tests for matcher of receipt product items and product metadata.
    """

    product = Product(
        shop="id",
        labels=[LabelMatch(name="due")],
        prices=[
            PriceMatch(value=Price("0.89"), indicator="minimum"),
            PriceMatch(value=Price("1.99"), indicator="maximum"),
        ],
        discounts=[DiscountMatch(label="over")],
        sku="abc123",
        gtin=1234567890123,
    )

    def _load_samples(
        self,
        session: Session,
        insert_products: bool = True,
        insert_receipt: bool = True,
    ) -> tuple[list[Product], Receipt]:
        receipt = next(ReceiptReader(Path("samples/receipt.yml")).read())
        products = list(ProductsReader(Path("samples/products-id.yml")).read())
        if insert_products:
            session.add_all(products)
        if insert_receipt:
            session.add(receipt)
            session.flush()
        return products, receipt

    def _test_samples(
        self,
        session: Session,
        insert_products: bool = True,
        insert_receipt: bool = True,
    ) -> tuple[list[Product], list[ProductItem]]:
        products, receipt = self._load_samples(
            session,
            insert_products=insert_products,
            insert_receipt=insert_receipt,
        )
        items = receipt.products

        matcher = ProductMatcher()
        self.assertEqual(
            items[1].discounts[0].label, products[2].discounts[0].label
        )
        self.assertEqual(
            items[1].price,
            Decimal(items[1].amount) * products[2].prices[1].value,
        )
        search_items = () if insert_receipt else items
        extra_products = () if insert_products else products
        self.assertEqual(
            list(
                matcher.find_candidates(session, search_items, extra_products)
            ),
            [
                # [2, bulk, 5.00, bonus]; [disco, -2.00, bulk; sub
                (products[2], items[1]),
                (products[2].range[1], items[1]),
                # [4, bulk, 8.00, bonus]; [disco, -2.00, bulk; sub
                (products[2], items[3]),
                (products[2].range[0], items[3]),
                # [0.750kg, weigh, 2.50]
                (products[0], items[4]),
                # [1, due, 0.89, 25%]
                (products[1], items[5]),
            ],
        )
        self.assertEqual(
            list(matcher.find_candidates(session, items[:4], extra_products)),
            [
                (products[2], items[1]),
                (products[2].range[1], items[1]),
                (products[2], items[3]),
                (products[2].range[0], items[3]),
            ],
        )

        return products, items

    def test_find_candidates(self) -> None:
        """
        Test detecting candidate products in the database that match the items.
        """

        with self.database as session:
            products, items = self._test_samples(session)

            items[3].product = products[2]
            session.flush()
            matcher = ProductMatcher()
            self.assertEqual(
                list(
                    matcher.find_candidates(
                        session, items[:4], only_unmatched=True
                    )
                ),
                [(products[2], items[1]), (products[2].range[1], items[1])],
            )

            items[3].discounts = []
            session.flush()
            matcher.discounts = False
            self.assertEqual(
                list(matcher.find_candidates(session, items[:4])),
                [
                    (products[2], items[1]),
                    (products[2].range[1], items[1]),
                    (products[2], items[2]),
                    (products[2].range[1], items[2]),
                    (products[2], items[3]),
                    (products[2].range[0], items[3]),
                ],
            )

            matcher.discounts = True

            fake_session = MagicMock()
            fake_shop = Product(
                shop="other", prices=[PriceMatch(value=Price("5.00"))]
            )
            fake_price = Product(
                shop="id", prices=[PriceMatch(value=Price("9.99"))]
            )
            fake_range = Product(
                shop="id",
                prices=[
                    PriceMatch(value=Price("2.00"), indicator="minimum"),
                    PriceMatch(value=Price("2.49"), indicator="maximum"),
                ],
            )
            fake_open_range = Product(
                shop="id",
                prices=[
                    PriceMatch(value=Price("2.49"), indicator="maximum"),
                ],
            )
            fake_year = Product(
                shop="id", prices=[PriceMatch(value="2.50", indicator="2014")]
            )
            fake_discount = Product(
                shop="id", discounts=[DiscountMatch(label="foobar")]
            )
            session_attrs = {
                "execute.return_value": [
                    MagicMock(Product=products[0], ProductItem=items[1]),
                    MagicMock(Product=products[1], ProductItem=items[1]),
                    MagicMock(Product=products[2], ProductItem=items[1]),
                    MagicMock(
                        Product=products[2].range[0], ProductItem=items[1]
                    ),
                    MagicMock(
                        Product=products[2].range[1], ProductItem=items[1]
                    ),
                    MagicMock(Product=fake_shop, ProductItem=items[1]),
                    MagicMock(Product=fake_price, ProductItem=items[1]),
                    MagicMock(Product=fake_range, ProductItem=items[1]),
                    MagicMock(Product=fake_open_range, ProductItem=items[1]),
                    MagicMock(Product=fake_year, ProductItem=items[1]),
                    MagicMock(Product=fake_discount, ProductItem=items[1]),
                ]
            }
            fake_session.configure_mock(**session_attrs)
            # Post-processing filter removes invalid matches.
            self.assertEqual(
                list(matcher.find_candidates(fake_session)),
                [(products[2], items[1]), (products[2].range[1], items[1])],
            )

    def test_find_candidates_dirty(self) -> None:
        """
        Test detecting candidate products in the database that match the items
        which have not been flushed in the session yet.
        """

        with self.database as session:
            products, items = self._test_samples(session, insert_receipt=False)
            items[3].product_id = products[2].id
            matcher = ProductMatcher()
            self.assertEqual(
                list(
                    matcher.find_candidates(
                        session, items[:4], only_unmatched=True
                    )
                ),
                [(products[2], items[1]), (products[2].range[1], items[1])],
            )

    def test_find_candidates_extra(self) -> None:
        """
        Test detecting candidate products from outside the database that match
        the items from the database.
        """

        with self.database as session:
            _ = self._test_samples(session, insert_products=False)

    def test_find_candidates_extra_dirty(self) -> None:
        """
        Test detecting candidate products from outside the database that match
        the items from the database.
        """

        with self.database as session:
            _ = self._test_samples(
                session, insert_products=False, insert_receipt=False
            )

    def test_find_candidates_extra_detached(self) -> None:
        """
        Test detecting candidate products which were edited but not yet flushed
        in a session that match the items.
        """

        with self.database as session:
            session.expire_on_commit = False
            _ = self._test_samples(session)
            product = session.scalar(
                select(Product)
                .options(
                    selectinload(Product.range), selectinload(Product.generic)
                )
                .filter(Product.type == "broccoli")
            )
            if product is None:
                self.fail("Expected product to be stored")
            self.assertIsNone(product.description)
            self.assertIsNotNone(product.id)

        product.description = "packaged"
        with self.database as session:
            matcher = ProductMatcher()
            item = session.scalar(
                select(ProductItem).filter(ProductItem.label == "weigh")
            )
            if item is None:
                self.fail("Expected product item to be stored")
            self.assertEqual(
                list(matcher.find_candidates(session, (item,), (product,))),
                [(product, item)],
            )
            self.assertEqual(product.description, "packaged")
            db_product = session.scalar(
                select(Product).filter(Product.type == "broccoli")
            )
            if db_product is None:
                self.fail("Expected product to be stored")
            self.assertIsNone(db_product.description)

    def test_select_duplicate(self) -> None:
        """
        Test determining which candidate product should be matched against
        a product item.
        """

        matcher = ProductMatcher()

        dupe = Product(id=99, shop="id")
        self.assertIs(
            matcher.select_duplicate(dupe, Product(id=99, shop="id")), dupe
        )
        self.assertIsNone(matcher.select_duplicate(dupe, Product(shop="id")))

        simple = Product(shop="id", range=[Product(shop="id")])
        self.assertIs(matcher.select_duplicate(simple.range[0], simple), simple)
        self.assertIs(matcher.select_duplicate(simple, simple.range[0]), simple)
        self.assertIsNone(matcher.select_duplicate(simple, Product(shop="id")))
        self.assertIs(matcher.select_duplicate(simple, simple), simple)

        none = Product(
            shop="id",
            labels=[LabelMatch(name="foo")],
            range=[Product(shop="id", labels=[])],
        )
        self.assertIs(matcher.select_duplicate(none.range[0], none), none)
        self.assertIs(matcher.select_duplicate(none, none.range[0]), none)

        two = Product(
            shop="id",
            labels=[LabelMatch(name="bar")],
            range=[
                Product(
                    shop="id",
                    labels=[LabelMatch(name="bar"), LabelMatch(name="baz")],
                )
            ],
        )
        self.assertIs(matcher.select_duplicate(two.range[0], two), two)
        self.assertIs(matcher.select_duplicate(two, two.range[0]), two)

        extra = Product(
            shop="id",
            labels=[LabelMatch(name="qux")],
            range=[
                Product(
                    shop="id",
                    labels=[LabelMatch(name="qux")],
                    prices=[PriceMatch(value=Price("1.00"))],
                ),
                Product(
                    shop="id",
                    labels=[LabelMatch(name="qux")],
                    description="extra",
                ),
            ],
        )
        self.assertIs(
            matcher.select_duplicate(extra.range[0], extra), extra.range[0]
        )
        self.assertIs(
            matcher.select_duplicate(extra, extra.range[0]), extra.range[0]
        )

        self.assertIsNone(matcher.select_duplicate(none.range[0], two.range[0]))
        self.assertIs(
            matcher.select_duplicate(extra.range[0], extra.range[1]), extra
        )
        self.assertIs(
            matcher.select_duplicate(extra.range[1], extra.range[0]), extra
        )

        matcher.discounts = False
        ignore = Product(
            shop="id",
            labels=[LabelMatch(name="qux")],
            range=[
                Product(
                    shop="id",
                    labels=[LabelMatch(name="qux")],
                    discounts=[DiscountMatch(label="due")],
                )
            ],
        )
        self.assertIs(matcher.select_duplicate(ignore.range[0], ignore), ignore)
        self.assertIs(matcher.select_duplicate(ignore, ignore.range[0]), ignore)

    def test_match(self) -> None:
        """
        Test checking if a candidate product matches a product item.
        """

        matcher = ProductMatcher()
        self.assertFalse(
            matcher.match(
                Product(shop="id"), ProductItem(receipt=Receipt(shop="ex"))
            )
        )
        receipt = Receipt(shop="id", date=date(2025, 5, 14))
        self.assertFalse(
            matcher.match(Product(shop="id"), ProductItem(receipt=receipt))
        )
        one = Quantity("1")
        for labels, label in (([LabelMatch(name="foo")], "bar"),):
            with self.subTest(labels=labels, label=label):
                self.assertFalse(
                    matcher.match(
                        Product(shop="id", labels=labels),
                        ProductItem(
                            receipt=receipt,
                            quantity=one,
                            label=label,
                            price=Price("1.00"),
                            amount=one.amount,
                            unit=one.unit,
                        ),
                    ),
                    f"{labels!r} should not match {label!r}",
                )

        price_tests: PriceTests = (
            ([PriceMatch(value=Price("0.99"))], Price("1.00"), Quantity("1")),
            (
                [
                    PriceMatch(value=Price("0.89"), indicator="minimum"),
                    PriceMatch(value=Price("1.99"), indicator="maximum"),
                ],
                Price("2.00"),
                one,
            ),
            (
                [PriceMatch(value=Price("1.23"), indicator="2024")],
                Price("1.23"),
                one,
            ),
            ([PriceMatch(value=Price("2.00"))], Price("2.00"), Quantity("2")),
            (
                [PriceMatch(value=Price("1.00"), indicator="kilogram")],
                Price("1.00"),
                Quantity("1l"),
            ),
            ([PriceMatch(value=Price("1.00"))], Price("1.00"), Quantity("1kg")),
        )
        for prices, price, count in price_tests:
            with self.subTest(prices=prices, price=price, quantity=count):
                self.assertFalse(
                    matcher.match(
                        Product(shop="id", prices=prices),
                        ProductItem(
                            receipt=receipt,
                            quantity=count,
                            price=price,
                            amount=count.amount,
                            unit=count.unit,
                        ),
                    ),
                    f"{prices!r} should not match {price!r}",
                )

        for discounts, discount in (([DiscountMatch(label="none")], "bulk"),):
            bonus = Discount(receipt=receipt, label=discount)
            with self.subTest(discounts=discounts, discount=discount):
                self.assertFalse(
                    matcher.match(
                        Product(shop="id", discounts=discounts),
                        ProductItem(
                            receipt=receipt,
                            quantity=one,
                            price=Price("1.00"),
                            discounts=[bonus],
                        ),
                    ),
                    f"{discounts!r} should not match {discount!r}",
                )
                matcher.discounts = False
                self.assertTrue(
                    matcher.match(
                        Product(
                            shop="id",
                            prices=price_tests[-1][0],
                            discounts=discounts,
                        ),
                        ProductItem(
                            receipt=receipt, quantity=one, price=Price("1.00")
                        ),
                    ),
                    f"{discounts!r} matters in no-discount mode",
                )
                matcher.discounts = True

        self.assertTrue(
            matcher.match(
                Product(
                    shop="id",
                    labels=[LabelMatch(name="due")],
                    prices=price_tests[1][0],
                    discounts=[DiscountMatch(label="over")],
                ),
                ProductItem(
                    receipt=receipt,
                    quantity=one,
                    label="due",
                    price=Price("0.89"),
                    discounts=[Discount(receipt=receipt, label="over")],
                    amount=one.amount,
                    unit=one.unit,
                ),
            )
        )

        weigh = Quantity("0.5kg")
        self.assertTrue(
            matcher.match(
                Product(shop="id", prices=price_tests[-2][0]),
                ProductItem(
                    receipt=receipt,
                    quantity=weigh,
                    label="weigh",
                    price=Price("0.50"),
                    amount=weigh.amount,
                    unit=weigh.unit,
                ),
            )
        )

        # Intervals with one bound match the product.
        self.assertTrue(
            matcher.match(
                Product(
                    shop="id",
                    prices=[
                        PriceMatch(value=Price("2.59"), indicator="minimum")
                    ],
                ),
                ProductItem(
                    receipt=receipt,
                    quantity=one,
                    price=Price("3.00"),
                    amount=one.amount,
                    unit=one.unit,
                ),
            ),
        )

    def test_load_map(self) -> None:
        """
        Test creating a mapping of unique keys of candidate products.
        """

        # No exception raised
        with self.database as session:
            _ = self._load_samples(session, insert_receipt=False)
            ProductMatcher().load_map(session)

    def test_clear_map(self) -> None:
        """
        Test clearing the mapping of unique keys.
        """

        # No exception raised
        ProductMatcher().clear_map()

    def test_add_map(self) -> None:
        """
        Test manually adding a candidate product to a mapping of unique keys.
        """

        matcher = ProductMatcher()
        self.assertFalse(matcher.add_map(self.product))

        with self.database as session:
            matcher.load_map(session)

        self.assertTrue(matcher.add_map(self.product))
        self.assertFalse(matcher.add_map(copy(self.product)))
        self.assertFalse(matcher.add_map(Product(shop="id")))
        self.assertFalse(matcher.add_map(Product(shop="id", sku="abc123")))
        self.assertTrue(matcher.add_map(Product(shop="other", sku="abc123")))
        self.assertFalse(
            matcher.add_map(Product(shop="id", gtin=1234567890123))
        )
        self.assertTrue(
            matcher.add_map(Product(shop="other", gtin=1234567890123))
        )
        self.assertTrue(
            matcher.add_map(
                Product(
                    shop="id",
                    gtin=1234567890123,
                    range=[Product(shop="id", sku="def456")],
                )
            )
        )

        matcher.clear_map()
        self.assertTrue(matcher.add_map(copy(self.product)))

    def test_discard_map(self) -> None:
        """
        Test removing a candidate model from a mapping of unique keys.
        """

        matcher = ProductMatcher()
        self.assertFalse(matcher.discard_map(self.product))

        with self.database as session:
            matcher.load_map(session)

        self.assertFalse(matcher.discard_map(self.product))
        _ = matcher.add_map(self.product)
        self.assertFalse(matcher.discard_map(Product(shop="id", sku="abc123")))
        self.assertFalse(matcher.discard_map(copy(self.product)))
        self.assertTrue(matcher.discard_map(self.product))
        self.assertFalse(matcher.discard_map(self.product))

        self.assertIsNone(matcher.check_map(self.product))

        generic = Product(
            shop="id", sku="abc123", range=[Product(shop="id", sku="def456")]
        )
        _ = matcher.add_map(generic)
        # Not the same product
        self.assertFalse(matcher.discard_map(Product(shop="id", sku="abc123")))
        self.assertTrue(matcher.discard_map(generic))
        self.assertFalse(matcher.discard_map(generic))

    def test_check_map(self) -> None:
        """
        Test retrieving a candidate product which has one or more unique keys.
        """

        matcher = ProductMatcher()
        self.assertIsNone(matcher.check_map(self.product))

        with self.database as session:
            matcher.load_map(session)

        _ = matcher.add_map(self.product)
        self.assertIs(matcher.check_map(self.product), self.product)
        self.assertIs(
            matcher.check_map(Product(shop="id", sku="abc123")), self.product
        )
        self.assertIs(
            matcher.check_map(Product(shop="id", gtin=1234567890123)),
            self.product,
        )
        self.assertIsNone(matcher.check_map(Product(shop="id")))

        limited = ProductMatcher(map_keys={MapKey.MAP_GTIN})
        with self.database as session:
            limited.load_map(session)

        _ = limited.add_map(self.product)
        self.assertIsNone(limited.check_map(Product(shop="id", sku="abc123")))
        self.assertIs(
            limited.check_map(Product(shop="id", gtin=1234567890123)),
            self.product,
        )

        far = Product(
            shop="id",
            range=[
                Product(shop="id"),
                Product(shop="id", gtin=9876543210987, sku="def"),
            ],
        )
        _ = matcher.add_map(far)
        _ = limited.add_map(far)
        self.assertIs(matcher.check_map(far), far)
        self.assertIs(limited.check_map(far), far)

        self.assertIsNone(
            matcher.check_map(
                Product(shop="id", range=[Product(shop="id", sku="abc123-o")])
            )
        )

    def test_find_map(self) -> None:
        """
        Test finding a product in the filled map based on a hash key.
        """

        matcher = ProductMatcher()

        product = matcher.find_map(
            (
                MapKey.MAP_MATCH,
                ("id", ("foo", "bar"), ((None, Price("1.23")),), ("disco",)),
            )
        )
        self.assertEqual(product.shop, "id")
        self.assertEqual(
            [label.name for label in product.labels], ["foo", "bar"]
        )
        self.assertEqual(
            [(price.indicator, price.value) for price in product.prices],
            [(None, Price("1.23"))],
        )
        self.assertEqual(
            [discount.label for discount in product.discounts], ["disco"]
        )

        unit = matcher.find_map((MapKey.MAP_SKU, ("id", "abc123")))
        self.assertEqual(unit.shop, "id")
        self.assertEqual(unit.sku, "abc123")

        item = matcher.find_map((MapKey.MAP_GTIN, ("other", 1234567890123)))
        self.assertEqual(item.shop, "other")
        self.assertEqual(item.gtin, 1234567890123)

        with self.assertRaisesRegex(
            TypeError, "Cannot construct empty Product metadata"
        ):
            self.assertIsNone(matcher.find_map("oops"))
        with self.assertRaisesRegex(
            TypeError, "Cannot construct empty Product metadata"
        ):
            self.assertIsNone(matcher.find_map(("some", ("other", "value"))))
        with self.assertRaisesRegex(
            TypeError, "Cannot construct empty Product metadata"
        ):
            self.assertIsNone(matcher.find_map((MapKey.MAP_MATCH,)))
        with self.assertRaisesRegex(
            TypeError, "Cannot construct empty Product metadata"
        ):
            self.assertIsNone(matcher.find_map((MapKey.MAP_SKU, ("shop",))))

        with self.database as session:
            matcher.load_map(session)

        _ = matcher.add_map(self.product)
        self.assertIs(
            matcher.find_map((MapKey.MAP_SKU, ("id", "abc123"))), self.product
        )

"""
Tests for database entity matching methods.
"""

from copy import copy
from datetime import date
from pathlib import Path
import unittest
from unittest.mock import MagicMock
from sqlalchemy.orm import Mapped, mapped_column, Session
from rechu.io.products import ProductsReader
from rechu.io.receipt import ReceiptReader
from rechu.models.base import Base as ModelBase, Price
from rechu.models.product import Product, LabelMatch, PriceMatch, DiscountMatch
from rechu.models.receipt import Receipt, ProductItem, Discount
from rechu.matcher import Matcher, ProductMatcher
from tests.database import DatabaseTestCase

class TestEntity(ModelBase): # pylint: disable=too-few-public-methods
    """
    Test entity.
    """

    __tablename__ = "test"

    id: Mapped[int] = mapped_column(primary_key=True)

class MatcherTest(unittest.TestCase):
    """
    Test for generic item candidate model matcher.
    """

    def test_find_candidates(self) -> None:
        """
        Test detecting candidate models.
        """

        with self.assertRaises(NotImplementedError):
            Matcher().find_candidates(MagicMock())

    def test_filter_duplicate_candidates(self) -> None:
        """
        Test detecting if item models were matched against multiple candidates.
        """

        matcher: Matcher[TestEntity, TestEntity] = Matcher()
        one = TestEntity(id=1)
        two = TestEntity(id=2)
        three = TestEntity(id=3)
        four = TestEntity(id=4)
        self.assertEqual(list(matcher.filter_duplicate_candidates([])), [])
        filtered = matcher.filter_duplicate_candidates([(two, one),
                                                        (three, one),
                                                        (four, two)])
        self.assertEqual(list(filtered), [(four, two)])

    def test_match(self) -> None:
        """
        Test checking if a candidate model matches an item model.
        """

        with self.assertRaises(NotImplementedError):
            Matcher().match(MagicMock(), MagicMock())

    def test_load_map(self) -> None:
        """
        Test creating a mapping of unique keys of candidate models.
        """

        # No exception raised
        Matcher().load_map(MagicMock())

    def test_add_map(self) -> None:
        """
        Test manually adding a candidate model to a mapping of unique keys.
        """

        self.assertFalse(Matcher().add_map(MagicMock()))

    def test_check_map(self) -> None:
        """
        Test retrieving a candidate model which has one or more unique keys.
        """

        self.assertIsNone(Matcher().check_map(MagicMock()))

class ProductMatcherTest(DatabaseTestCase):
    """
    Tests for matcher of receipt product items and product metadata.
    """

    def _test_samples(self, session: Session, insert_receipt: bool = True) \
            -> tuple[list[Product], list[ProductItem]]:
        receipt = next(ReceiptReader(Path("samples/receipt.yml")).read())
        products = list(ProductsReader(Path("samples/products-id.yml")).read())
        session.add_all(products)
        if insert_receipt:
            session.add(receipt)
            session.flush()
        items = receipt.products

        matcher = ProductMatcher()
        self.assertEqual(items[1].discounts[0].label,
                         products[2].discounts[0].label)
        self.assertEqual(items[1].price, products[2].prices[0].value)
        search_items = None if insert_receipt else items
        self.assertEqual(list(matcher.find_candidates(session, search_items)),
                         [
                             # [2, bulk, 5.00, bonus]; [disco, -2.00, bulk
                             (products[2], items[1]),
                             # [4, bulk, 8.00, bonus]; [disco, -2.00, bulk
                             (products[2], items[3]),
                             # [0.750kg, weigh, 2.50]
                             (products[0], items[4]),
                             # [1, due, 0.89, 25%]
                             (products[1], items[5])
                         ])
        self.assertEqual(list(matcher.find_candidates(session, items[:4])),
                         [(products[2], items[1]), (products[2], items[3])])

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
            self.assertEqual(list(matcher.find_candidates(session, items[:4],
                                                          only_unmatched=True)),
                             [(products[2], items[1])])

            fake_session = MagicMock()
            fake_shop = Product(shop='other',
                                prices=[PriceMatch(value=Price('5.00'))])
            fake_price = Product(shop='id',
                                 prices=[PriceMatch(value=Price('9.99'))])
            fake_range = Product(shop='id',
                                 prices=[PriceMatch(value=Price('4.00'),
                                                    indicator='minimum'),
                                         PriceMatch(value=Price('4.99'),
                                                    indicator='maximum')])
            fake_year = Product(shop='id',
                                prices=[PriceMatch(value='5.00',
                                                   indicator='2014')])
            fake_discount = Product(shop='id',
                                    discounts=[DiscountMatch(label='foobar')])
            session_attrs = {
                'execute.return_value': [
                    MagicMock(Product=products[0], ProductItem=items[1]),
                    MagicMock(Product=products[1], ProductItem=items[1]),
                    MagicMock(Product=products[2], ProductItem=items[1]),
                    MagicMock(Product=fake_shop, ProductItem=items[1]),
                    MagicMock(Product=fake_price, ProductItem=items[1]),
                    MagicMock(Product=fake_range, ProductItem=items[1]),
                    MagicMock(Product=fake_year, ProductItem=items[1]),
                    MagicMock(Product=fake_discount, ProductItem=items[1])
                ]
            }
            fake_session.configure_mock(**session_attrs)
            # Post-processing filter removes invalid matches.
            self.assertEqual(list(matcher.find_candidates(fake_session)),
                             [(products[2], items[1])])

    def test_find_candidates_dirty(self) -> None:
        """
        Test detecting candidate products in the database that match the items
        which have not been flushed in the session yet.
        """

        with self.database as session:
            products, items = self._test_samples(session, insert_receipt=False)
            items[3].product_id = products[2].id
            matcher = ProductMatcher()
            self.assertEqual(list(matcher.find_candidates(session, items[:4],
                                                          only_unmatched=True)),
                             [(products[2], items[1])])

    def test_match(self) -> None:
        """
        Test checking if a candidate product matches a product item.
        """

        matcher = ProductMatcher()
        self.assertFalse(matcher.match(Product(shop='id'),
                                       ProductItem(receipt=Receipt(shop='ex'))))
        receipt = Receipt(shop='id', date=date(2025, 5, 14))
        self.assertFalse(matcher.match(Product(shop='id'),
                                       ProductItem(receipt=receipt)))
        for (labels, label) in (([LabelMatch(name='foo')], 'bar'),):
            with self.subTest(labels=labels, label=label):
                self.assertFalse(matcher.match(Product(shop='id',
                                                       labels=labels),
                                               ProductItem(receipt=receipt,
                                                           label=label)),
                                 f"{labels!r} should not match {label!r}")

        price_tests = (
            ([PriceMatch(value=Price('0.99'))], Price('1.00')),
            ([
                PriceMatch(value=Price('0.89'), indicator='minimum'),
                PriceMatch(value=Price('1.99'), indicator='maximum')
            ], Price('2.00')),
            # For now, matchers with only one bound are not considered
            ([
                PriceMatch(value=Price('2.59'), indicator='minimum')
            ], Price('3.00')),
            ([PriceMatch(value=Price('1.23'), indicator='2024')], Price('1.23'))
        )
        for (prices, price) in price_tests:
            with self.subTest(prices=prices, price=price):
                self.assertFalse(matcher.match(Product(shop='id',
                                                       prices=prices),
                                               ProductItem(receipt=receipt,
                                                           price=price)),
                                 f"{prices!r} should not match {price!r}")

        for (discounts, discount) in (([DiscountMatch(label='none')], 'bulk'),):
            bonus = Discount(receipt=receipt, label=discount)
            with self.subTest(discounts=discounts, discount=discount):
                self.assertFalse(matcher.match(Product(shop='id',
                                                       discounts=discounts),
                                               ProductItem(receipt=receipt,
                                                           price=Price('1.00'),
                                                           discounts=[bonus])),
                                 f"{discounts!r} should not match {discount!r}")

        product = Product(shop='id',
                          labels=[LabelMatch(name='due')],
                          prices=price_tests[1][0],
                          discounts=[DiscountMatch(label='over')])
        drop = Discount(receipt=receipt, label='over')
        self.assertTrue(matcher.match(product, ProductItem(receipt=receipt,
                                                           label='due',
                                                           price=Price('0.89'),
                                                           discounts=[drop])))

    def test_load_map(self) -> None:
        """
        Test creating a mapping of unique keys of candidate products.
        """

        # No exception raised
        with self.database as session:
            ProductMatcher().load_map(session)

    def test_add_map(self) -> None:
        """
        Test manually adding a candidate product to a mapping of unique keys.
        """

        matcher = ProductMatcher()
        product = Product(shop='id',
                          labels=[LabelMatch(name='due')],
                          prices=[
                              PriceMatch(value=Price('0.89'),
                                         indicator='minimum'),
                              PriceMatch(value=Price('1.99'),
                                         indicator='maximum')
                          ],
                          discounts=[DiscountMatch(label='over')],
                          sku='abc123',
                          gtin=1234567890123)
        self.assertFalse(matcher.add_map(product))

        session_attrs = {'scalars.return_value': []}
        matcher.load_map(MagicMock(**session_attrs))

        self.assertTrue(matcher.add_map(product))
        self.assertFalse(matcher.add_map(copy(product)))
        self.assertFalse(matcher.add_map(Product(shop='id')))
        self.assertFalse(matcher.add_map(Product(shop='id', sku='abc123')))
        self.assertFalse(matcher.add_map(Product(shop='id',
                                                 gtin=1234567890123)))

    def test_check_map(self) -> None:
        """
        Test retrieving a candidate product which has one or more unique keys.
        """

        matcher = ProductMatcher()
        product = Product(shop='id',
                          labels=[LabelMatch(name='due')],
                          prices=[
                              PriceMatch(value=Price('0.89'),
                                         indicator='minimum'),
                              PriceMatch(value=Price('1.99'),
                                         indicator='maximum')
                          ],
                          discounts=[DiscountMatch(label='over')],
                          sku='abc123',
                          gtin=1234567890123)
        self.assertIsNone(matcher.check_map(product))

        session_attrs = {'scalars.return_value': []}
        matcher.load_map(MagicMock(**session_attrs))

        matcher.add_map(product)
        self.assertIs(matcher.check_map(product), product)
        self.assertIs(matcher.check_map(Product(shop='id', sku='abc123')),
                                        product)
        self.assertIs(matcher.check_map(Product(shop='id',
                                                gtin=1234567890123)), product)
        self.assertIsNone(matcher.check_map(Product(shop='id')))

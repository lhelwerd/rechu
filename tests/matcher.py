"""
Tests for database entity matching methods.
"""

from pathlib import Path
import unittest
from unittest.mock import MagicMock
from sqlalchemy.orm import Session
from rechu.io.products import ProductsReader
from rechu.io.receipt import ReceiptReader
from rechu.models.base import Price
from rechu.models.product import Product, PriceMatch, DiscountMatch
from rechu.models.receipt import ProductItem
from rechu.matcher import Matcher, ProductMatcher
from tests.database import DatabaseTestCase

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

        matcher: Matcher[int, int] = Matcher()
        self.assertEqual(list(matcher.filter_duplicate_candidates([])), [])
        filtered = matcher.filter_duplicate_candidates([(2, 1), (3, 1), (4, 2)])
        self.assertEqual(list(filtered), [(4, 2)])

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

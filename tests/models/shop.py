"""
Tests for shop metadata models.
"""

import unittest
from rechu.models.shop import Shop, DiscountIndicator

class ShopTest(unittest.TestCase):
    """
    Tests for shop metadata model.
    """

    def setUp(self) -> None:
        super().setUp()

        # These may be changed during test so no class members
        self.shop = Shop(key='id', name='Generic Shop',
                         website='https://shop.example',
                         products='{website}/p/{category}/{sku}')
        self.other = Shop(key='id', name='iDiscount',
                          website='https://example.com',
                          products='{website}/products/{sku}',
                          discount_indicators=[
                              DiscountIndicator(pattern=r'[a-z]+'),
                              DiscountIndicator(pattern=r'\d+%')
                          ])
        self.inv = Shop(key='inv', name='Inventory')

    def test_copy(self) -> None:
        """
        Test copying the shop.
        """

        copy = self.shop.copy()
        self.assertIsNot(self.shop, copy)
        self.assertEqual(self.shop.key, copy.key)
        self.assertEqual(self.shop.name, copy.name)
        self.assertEqual([ind.pattern for ind in self.shop.discount_indicators],
                         [ind.pattern for ind in copy.discount_indicators])
        self.assertFalse(self.shop.merge(copy))

    def test_merge(self) -> None:
        """
        Test merging attributes of another product.
        """

        self.assertTrue(self.shop.merge(self.other))

        self.assertEqual(self.shop.key, 'id')
        self.assertEqual(self.shop.name, 'iDiscount')
        self.assertEqual(self.shop.website, 'https://example.com')
        self.assertIsNone(self.shop.wikidata)
        self.assertEqual(self.shop.products, '{website}/products/{sku}')
        self.assertEqual([ind.pattern for ind in self.shop.discount_indicators],
                         [r'[a-z]+', r'\d+%'])

        self.assertFalse(self.shop.merge(self.other))

        with self.assertRaisesRegex(ValueError, "shops must have the same key"):
            self.assertFalse(self.shop.merge(self.inv))

        self.assertFalse(self.inv.merge(Shop(key='inv', name='Invalid'),
                                        override=False))
        self.assertEqual(self.inv.key, 'inv')
        self.assertEqual(self.inv.name, 'Inventory')

    def test_repr(self) -> None:
        """
        Test the string representation of the model.
        """

        self.assertEqual(repr(self.shop),
                         "Shop(key='id', name='Generic Shop', "
                         "website='https://shop.example', wikidata=None, "
                         "products='{website}/p/{category}/{sku}', "
                         "discount_indicators=[])")

class DiscountIndicatorTest(unittest.TestCase):
    """
    Tests for indicator model.
    """

    def test_repr(self) -> None:
        """
        Test the string representation of the model.
        """

        self.assertEqual(repr(DiscountIndicator(pattern=r'\w+')), r"r'\w+'")
        self.assertEqual(repr(DiscountIndicator(pattern=r"'?'")), r"r'\'?\''")

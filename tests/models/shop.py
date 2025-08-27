"""
Tests for shop metadata models.
"""

import unittest
from rechu.models.shop import Shop

class ShopTest(unittest.TestCase):
    """
    Tests for shop metadata model.
    """

    def test_repr(self) -> None:
        """
        Test the string representation of the model.
        """

        self.assertEqual(repr(Shop(key='id', name='Generic Shop',
                                   website='https://shop.example',
                                   products='{website}/p/{category}/{sku}')),
                         "Shop(key='id', name='Generic Shop', "
                         "website='https://shop.example', wikidata=None, "
                         "products='{website}/p/{category}/{sku}', "
                         "discount_indicators=[])")

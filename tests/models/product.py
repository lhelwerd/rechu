"""
Tests for product metadata model.
"""

from rechu.models.product import Product
from tests.database import DatabaseTestCase

class ProductTest(DatabaseTestCase):
    """
    Tests for product model.
    """

    def test_repr(self) -> None:
        """
        Test the string representation of the model.
        """

        product = Product(shop='id', brand='abc', description='def',
                          category='foo', type='bar', portions=12,
                          weight='750g', volume='1l', alcohol='2.0%',
                          sku='1234', gtin=1234567890123)
        self.assertEqual(repr(product),
                         "Product(id=None, shop='id', brand='abc', "
                         "description='def', category='foo', type='bar', "
                         "portions=12, weight='750g', volume='1l', "
                         "alcohol='2.0%', sku='1234', gtin=1234567890123)")
        with self.database as session:
            session.add(product)
            session.flush()
            self.assertEqual(repr(product),
                             "Product(id=1, shop='id', brand='abc', "
                             "description='def', category='foo', type='bar', "
                             "portions=12, weight='750g', volume='1l', "
                             "alcohol='2.0%', sku='1234', gtin=1234567890123)")

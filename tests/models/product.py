"""
Tests for product metadata model.
"""

from rechu.models.product import Product, LabelMatch, PriceMatch, DiscountMatch
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
                         "Product(id=None, shop='id', labels=[], prices=[], "
                         "discounts=[], brand='abc', description='def', "
                         "category='foo', type='bar', portions=12, "
                         "weight='750g', volume='1l', alcohol='2.0%', "
                         "sku='1234', gtin=1234567890123)")
        product.labels = [LabelMatch(product=product, name='label')]
        product.prices = [
            PriceMatch(product=product, value=1.23, indicator='minimum'),
            PriceMatch(product=product, value=7.89, indicator='maximum')
        ]
        product.discounts = [DiscountMatch(product=product, label='disco')]
        with self.database as session:
            session.add(product)
            session.flush()
            self.assertEqual(repr(product),
                             "Product(id=1, shop='id', labels=['label'], "
                             "prices=[('minimum', 1.23), ('maximum', 7.89)], "
                             "discounts=['disco'], brand='abc', "
                             "description='def', category='foo', type='bar', "
                             "portions=12, weight='750g', volume='1l', "
                             "alcohol='2.0%', sku='1234', gtin=1234567890123)")

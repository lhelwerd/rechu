"""
Tests for product metadata model.
"""

from itertools import zip_longest
from rechu.models.base import Price
from rechu.models.product import Product, LabelMatch, PriceMatch, DiscountMatch
from tests.database import DatabaseTestCase

class ProductTest(DatabaseTestCase):
    """
    Tests for product model.
    """

    def test_merge(self) -> None:
        """
        Test merging attributes of another product.
        """

        prices = [
            PriceMatch(value=Price('0.01')),
            PriceMatch(value=Price('0.03')),
            PriceMatch(value=Price('0.98'), indicator='minimum'),
            PriceMatch(value=Price('0.50'), indicator='2024')
        ]
        product = Product(shop='id', labels=[LabelMatch(name='first')],
                          prices=prices, discounts=[DiscountMatch(label='one')],
                          brand='abc', description='def',
                          category='foo', type='bar', portions=12)
        other = Product(id=3, shop='ignore',
                        labels=[
                            LabelMatch(name='first'), LabelMatch(name='second')
                        ],
                        discounts=[
                            DiscountMatch(label='one'), DiscountMatch(label='2')
                        ],
                        weight='750g', volume='1l', alcohol='2.0%',
                        sku='1234', gtin=1234567890123)

        product.merge(other)

        # ID is updated but shop is not
        self.assertEqual(product.id, 3)
        self.assertEqual(product.shop, 'id')

        self.assertEqual(len(product.labels), 2)
        self.assertEqual(product.labels[0].name, 'first')
        self.assertEqual(product.labels[1].name, 'second')

        self.assertEqual(len(product.prices), 4)

        self.assertEqual(len(product.discounts), 2)
        self.assertEqual(product.discounts[0].label, 'one')
        self.assertEqual(product.discounts[1].label, '2')

        self.assertEqual(product.brand, 'abc')
        self.assertEqual(product.description, 'def')
        self.assertEqual(product.category, 'foo')
        self.assertEqual(product.type, 'bar')
        self.assertEqual(product.portions, 12)

        self.assertEqual(product.weight, '750g')
        self.assertEqual(product.volume, '1l')
        self.assertEqual(product.alcohol, '2.0%')
        self.assertEqual(product.sku, '1234')
        self.assertEqual(product.gtin, 1234567890123)

        new_prices = [
            PriceMatch(value=Price('0.01')),
            PriceMatch(value=Price('0.02')),
            PriceMatch(value=Price('0.98'), indicator='minimum'),
            PriceMatch(value=Price('1.99'), indicator='maximum'),
            PriceMatch(value=Price('0.50'), indicator='2024'),
            PriceMatch(value=Price('0.75'), indicator='2025')
        ]
        expected_prices = [
            ('0.01', None),
            ('0.03', None),
            ('0.98', 'minimum'),
            ('0.50', '2024'),
            ('0.02', None),
            ('1.99', 'maximum'),
            ('0.75', '2025')
        ]
        product.merge(Product(prices=new_prices))
        for i, (price, expected) in enumerate(zip_longest(product.prices,
                                                          expected_prices)):
            with self.subTest(index=i):
                if price is None:
                    self.fail("Not enough prices in merged product")
                if expected is None:
                    self.fail("Too many prices in merged product")
                self.assertEqual(price.value, Price(expected[0]))
                self.assertEqual(price.indicator, expected[1])


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

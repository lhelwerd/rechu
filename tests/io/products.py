"""
Tests for products matching metadata file handling.
"""

from io import StringIO
from itertools import zip_longest
from pathlib import Path
from typing import Optional, TypedDict, Union
import unittest
import yaml
from rechu.io.products import ProductsReader, ProductsWriter
from rechu.models.base import GTIN, Price
from rechu.models.product import Product, LabelMatch, PriceMatch, DiscountMatch

class _ProductData(TypedDict, total=False):
    shop: str
    labels: list[str]
    prices: Union[list[Price], dict[str, Price]]
    bonuses: list[str]
    category: Optional[str]
    type: Optional[str]
    portions: Optional[int]
    weight: Optional[str]
    sku: Optional[str]
    gtin: Optional[int]

expected: list[_ProductData] = [
    {
        'shop': 'id',
        'labels': ['weigh'],
        'category': 'vegetables',
        'type': 'broccoli'
    },
    {
        'shop': 'id',
        'labels': ['due'],
        'prices': {'minimum': Price('0.89'), 'maximum': Price('0.99')},
        'category': 'bread',
        'portions': 22,
        'weight': '150g',
        'gtin': 1234567890123
    },
    {
        'shop': 'id',
        'prices': [Price('5.00'), Price('7.50'), Price('8.00')],
        'bonuses': ['bonus'],
        'type': 'chocolate',
        'sku': 'abc123'
    }
]

class ProductsReaderTest(unittest.TestCase):
    """
    Tests for products metadata file reader.
    """

    def test_parse(self) -> None:
        """
        Test parsing an open file and yielding product models from it.
        """

        with self.assertRaisesRegex(TypeError,
                                    "File '.*' does not contain a mapping"):
            next(ProductsReader(Path('fake/file.yml')).parse(StringIO('123')))

        path = Path('samples/products-id.yml')
        with path.open('r', encoding='utf-8') as file:
            index = -1
            for index, product in enumerate(ProductsReader(path).parse(file)):
                with self.subTest(product=index):
                    self.assertEqual(product.shop, expected[index]['shop'])

                    labels = expected[index].get('labels', [])
                    self.assertEqual(len(product.labels), len(labels))
                    for label, matcher in zip(product.labels, labels):
                        self.assertEqual(label.name, matcher)

                    prices = expected[index].get('prices', {})
                    self.assertEqual(len(product.prices), len(prices))
                    if isinstance(prices, dict):
                        for price, (key, value) in zip(product.prices,
                                                       prices.items()):
                            self.assertEqual(price.value, value)
                            self.assertEqual(price.indicator, key)
                    else:
                        for price, value in zip(product.prices, prices):
                            self.assertEqual(price.value, value)
                            self.assertIsNone(price.indicator)

                    bonuses = expected[index].get('bonuses', [])
                    self.assertEqual(len(product.discounts), len(bonuses))
                    for discount, bonus in zip(product.discounts, bonuses):
                        self.assertEqual(discount.label, bonus)

                    self.assertEqual(product.category,
                                     expected[index].get('category'))
                    self.assertEqual(product.portions,
                                     expected[index].get('portions'))
                    self.assertEqual(product.weight,
                                     expected[index].get('weight'))
                    self.assertEqual(product.sku, expected[index].get('sku'))
                    self.assertEqual(product.gtin, expected[index].get('gtin'))

            self.assertEqual(index, len(expected) - 1)

class ProductsWriterTest(unittest.TestCase):
    """
    Tests for products metadata file writer.
    """

    def setUp(self) -> None:
        self.path = Path('samples/products-id.yml')
        self.models = (
            Product(shop='id', labels=[LabelMatch(name='weigh')],
                    category='vegetables', type='broccoli'),
            Product(shop='id', labels=[LabelMatch(name='due')],
                    prices=[
                        PriceMatch(value=Price('0.89'), indicator='minimum'),
                        PriceMatch(value=Price('0.99'), indicator='maximum')
                    ],
                    category='bread', portions=22, weight='150g',
                    gtin=1234567890123),
            Product(shop='id',
                    prices=[
                        PriceMatch(value=Price('5.00')),
                        PriceMatch(value=Price('7.50')),
                        PriceMatch(value=Price('8.00'))
                    ],
                    discounts=[DiscountMatch(label='bonus')],
                    type='chocolate',
                    sku='abc123')
        )

    def test_serialize(self) -> None:
        """
        Test writing a serialized variant of models to an open file.
        """

        writer = ProductsWriter(self.path, self.models)
        file = StringIO()
        writer.serialize(file)

        file.seek(0)
        actual = yaml.safe_load('\n'.join(file.readlines()))

        self.assertEqual(actual['shop'], 'id')
        self.assertEqual(len(actual['products']), len(expected))
        for index, product in enumerate(expected):
            with self.subTest(product=index):
                actual_product = actual['products'][index]
                self.assertNotIn('shop', actual_product)

                self.assertEqual(actual_product.get('labels', []),
                                 product.get('labels', []))

                actual_prices = actual_product.get('prices', {})
                prices = product.get('prices', {})
                self.assertEqual(len(actual_prices), len(prices))
                self.assertEqual(type(actual_prices), type(prices))
                if isinstance(prices, dict):
                    for (end, price), (key, value) in zip(actual_prices.items(),
                                                          prices.items()):
                        self.assertEqual(end, key)
                        self.assertEqual(price, float(value))
                else:
                    for price, value in zip(actual_prices, prices):
                        self.assertEqual(price, float(value))

                self.assertEqual(actual_product.get('bonuses', []),
                                 product.get('bonuses', []))

                self.assertEqual(actual_product.get('category'),
                                 product.get('category'))
                self.assertEqual(actual_product.get('type'),
                                 product.get('type'))
                self.assertEqual(actual_product.get('portions'),
                                 product.get('portions'))
                self.assertEqual(actual_product.get('weight'),
                                 product.get('weight'))
                self.assertEqual(actual_product.get('sku'),
                                 product.get('sku'))
                if 'gtin' not in actual_product:
                    self.assertNotIn('gtin', product)
                else:
                    self.assertEqual(GTIN(actual_product['gtin']),
                                     product.get('gtin'))

    def test_serialize_roundtrip(self) -> None:
        """
        Test writing a serialized variant of models to an open file and
        checking its serialization format.
        """

        writer = ProductsWriter(self.path, self.models)
        file = StringIO()
        writer.serialize(file)
        file.seek(0)
        lines = file.readlines()

        # Serialization should look the same way, including price precisions
        # and GTIN number format.
        with self.path.open("r", encoding="utf-8") as original_file:
            for (line, (original, new)) in enumerate(zip_longest(original_file,
                                                                 lines)):
                with self.subTest(line=line):
                    self.assertEqual(original, new)

    def test_serialize_common(self) -> None:
        """
        Test writing a serialized variant of models with common attributes to
        an open file.
        """

        # Writing models with more common attributes
        for model in self.models:
            model.type = 'foo'

        writer = ProductsWriter(self.path, self.models)
        file = StringIO()
        writer.serialize(file)

        file.seek(0)
        actual = yaml.safe_load('\n'.join(file.readlines()))
        self.assertEqual(actual['type'], 'foo')

    def test_serialize_invalid(self) -> None:
        """
        Test writing a serialized variant of invalid models to an open file.
        """

        writer = ProductsWriter(self.path, [])
        file = StringIO()
        with self.assertRaisesRegex(ValueError,
                                    'Not all products are from the same shop'):
            writer.serialize(file)

        self.models[-1].prices[0].indicator = 'oops'

        writer = ProductsWriter(self.path, self.models)
        with self.assertRaisesRegex(ValueError,
                                    'Not all price matchers have indicators'):
            writer.serialize(file)

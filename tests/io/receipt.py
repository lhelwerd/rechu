"""
Tests for receipt file handling.
"""

from datetime import datetime, date
from io import StringIO
from pathlib import Path
from typing import Optional, Union
import unittest
import yaml
from rechu.io.receipt import ReceiptReader, ReceiptWriter
from rechu.models.receipt import Discount, ProductItem, Receipt

expected: dict[str, list[dict[str, Optional[Union[str, float, list[int]]]]]] = {
    'products': [
        {
            'quantity': '1',
            'label': 'label',
            'price': 0.99,
            'discount_indicator': None
        },
        {
            'quantity': '2',
            'label': 'bulk',
            'price': 5.00,
            'discount_indicator': 'bonus'
        },
        {
            'quantity': '3',
            'label': 'bulk',
            'price': 7.50,
            'discount_indicator': None
        },
        {
            'quantity': '4',
            'label': 'bulk',
            'price': 8.00,
            'discount_indicator': 'bonus'
        },
        {
            'quantity': '0.750kg',
            'label': 'weigh',
            'price': 2.50,
            'discount_indicator': None
        },
        {
             'quantity': '1',
             'label': 'due',
             'price': 0.89,
             'discount_indicator': '25%'
        }
    ],
    'discounts': [
        {
            'label': 'disco',
            'price_decrease': -2.00,
            'items': [1, 3]
        },
        {
            'label': 'over',
            'price_decrease': -0.22,
            'items': [5]
        },
        {
            'label': 'none',
            'price_decrease': -0.02,
            'items': []
        },
        {
            'label': 'missing',
            'price_decrease': -0.20,
            'items': []
        }
    ]
}
class ReceiptReaderTest(unittest.TestCase):
    """
    Tests for receipt file reader.
    """

    def test_parse(self) -> None:
        """
        Test parsing an open file and yielding receipt models from it.
        """

        with self.assertRaisesRegex(TypeError,
                                    "File '.*' does not contain a mapping"):
            next(ReceiptReader(Path('fake/file.yml')).parse(StringIO('123')))

        path = Path('samples/receipt.yml')
        reader = ReceiptReader(path)
        with path.open('r', encoding='utf-8') as file:
            generator = reader.parse(file)
            receipt = next(generator)
            self.assertEqual(receipt.filename, 'receipt.yml')
            self.assertEqual(receipt.date, date(2024, 11, 1))
            self.assertEqual(receipt.shop, 'id')
            self.assertEqual(len(receipt.products), len(expected['products']))
            for index, product in enumerate(expected['products']):
                with self.subTest(product=index):
                    self.assertEqual(receipt.products[index].quantity,
                                     product['quantity'])
                    self.assertEqual(receipt.products[index].label,
                                     product['label'])
                    self.assertEqual(receipt.products[index].price,
                                     product['price'])
                    self.assertEqual(receipt.products[index].discount_indicator,
                                     product['discount_indicator'])
            self.assertEqual(len(receipt.discounts), len(expected['discounts']))
            for index, discount in enumerate(expected['discounts']):
                with self.subTest(discount=index):
                    self.assertEqual(receipt.discounts[index].label,
                                     discount['label'])
                    self.assertEqual(receipt.discounts[index].price_decrease,
                                     discount['price_decrease'])
                    items = discount['items']
                    if not isinstance(items, list):
                        self.fail('Invalid expected items')
                        return
                    self.assertEqual(len(receipt.discounts[index].items),
                                     len(items))
                    for number, item in zip(items,
                                            receipt.discounts[index].items):
                        with self.subTest(discountItem=number):
                            self.assertEqual(receipt.products[number], item)
                            self.assertIn(receipt.discounts[index],
                                          item.discounts)

        with self.assertRaises(StopIteration):
            next(generator)

class ReceiptWriterTest(unittest.TestCase):
    """
    Tests for receipt file writer.
    """

    def setUp(self) -> None:
        updated = datetime(2024, 11, 1, 12, 34, 0)
        self.model = Receipt(filename='file', updated=updated,
                             date=updated.date(), shop='id')
        self.model.products = [
            ProductItem(quantity='1', label='label', price=0.99,
                        discount_indicator=None),
            ProductItem(quantity='2', label='bulk', price=5.00,
                        discount_indicator='bonus'),
            ProductItem(quantity='3', label='bulk', price=7.50,
                        discount_indicator=None),
            ProductItem(quantity='4', label='bulk', price=8.00,
                        discount_indicator='bonus'),
            ProductItem(quantity='0.750kg', label='weigh', price=2.50,
                        discount_indicator=None),
            ProductItem(quantity='1', label='due', price=0.89,
                        discount_indicator='25%')
        ]
        self.model.discounts = [
            Discount(label='disco', price_decrease=-2.00,
                     items=[self.model.products[1], self.model.products[3]]),
            Discount(label='over', price_decrease=-0.22,
                     items=[self.model.products[5]]),
            Discount(label='none', price_decrease=-0.02, items=[]),
            Discount(label='missing', price_decrease=-0.20, items=[])
        ]

    def tearDown(self) -> None:
        Path('samples/new_receipt.yml').unlink(missing_ok=True)

    def test_serialize(self) -> None:
        """
        Test writing a serialized variant of a model to an open file.
        """

        path = Path('samples/receipt.yml')
        writer = ReceiptWriter(path, self.model)
        file = StringIO()
        writer.serialize(file)
        actual = yaml.safe_load(file.getvalue())
        self.assertEqual(actual['date'], date(2024, 11, 1))
        self.assertEqual(actual['shop'], 'id')
        self.assertEqual(len(actual['products']), len(expected['products']))
        for index, product in enumerate(expected['products']):
            with self.subTest(product=index):
                if product['discount_indicator'] is None:
                    self.assertEqual(actual['products'][index], [
                        product['quantity'], product['label'], product['price']
                    ])
                else:
                    self.assertEqual(actual['products'][index], [
                        product['quantity'], product['label'], product['price'],
                        product['discount_indicator']
                    ])
        self.assertEqual(len(actual['bonus']), len(expected['discounts']))
        for index, discount in enumerate(expected['discounts']):
            with self.subTest(discount=index):
                self.assertEqual(actual['bonus'][index][0], discount['label'])
                self.assertEqual(actual['bonus'][index][1],
                                 discount['price_decrease'])
                items = discount['items']
                if not isinstance(items, list):
                    self.fail('Invalid expected items')
                    return
                self.assertEqual(actual['bonus'][index][2:], [
                    str(expected['products'][item]['label']) for item in items
                ])

    def test_write(self) -> None:
        """
        Test writing a model to a path.
        """

        path = Path('samples/new_receipt.yml')
        writer = ReceiptWriter(path, self.model)
        writer.write()
        self.assertTrue(path.exists())
        self.assertEqual(path.stat().st_mtime, self.model.updated.timestamp())

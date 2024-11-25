"""
Tests for receipt file handling.
"""

from datetime import date
from io import StringIO
from pathlib import Path
from typing import Optional, Union
import unittest
from rechu.io.receipt import ReceiptReader

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
        expected: dict[str,
                       list[dict[str,
                                 Optional[Union[str, float, list[int]]]]]] = {
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

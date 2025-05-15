"""
Tests of subcommand to import receipt YAML files.
"""

from datetime import datetime
import os
from pathlib import Path
from typing import Union
from unittest.mock import patch
from sqlalchemy import select
from sqlalchemy.orm import Session
import yaml
from rechu.command.read import Read
from rechu.models.base import Price
from rechu.models.product import Product
from rechu.models.receipt import Receipt
from ..database import DatabaseTestCase

class ReadTest(DatabaseTestCase):
    """
    Test reading the YAML files and importing them to the database.
    """

    # Overrides file sorted after samples/products-id.yml
    extra_products = Path("samples/products-id.zzz.yml")
    min_price = Price('1.00')

    def tearDown(self) -> None:
        super().tearDown()
        self.extra_products.unlink(missing_ok=True)

    def _get_receipt(self, session: Session) -> Receipt:
        receipt = session.scalar(select(Receipt).limit(1))
        if receipt is None:
            self.fail("Expected receipt to be stored")
        return receipt

    def _alter_price(self, value: Union[float, str]) -> Price:
        price = Price(value)
        if price < self.min_price:
            return Price(price + self.min_price)
        return price

    def test_run(self) -> None:
        """
        Test executing the command.
        """

        now = datetime.now().timestamp()
        os.utime('samples', times=(now, now))
        os.utime('samples/receipt.yml', times=(now, now))

        command = Read()
        command.run()

        product_count = 3

        with self.database as session:
            self.assertEqual(len(session.scalars(select(Product)).all()),
                             product_count)
            receipt = self._get_receipt(session)
            self.assertEqual(receipt.filename, 'receipt.yml')
            updated = receipt.updated

            self.assertIsNone(receipt.products[0].product,
                              f"Unexpected match for {receipt.products[0]!r}")
            self.assertIsNotNone(receipt.products[1].product,
                                 f"Expected match for {receipt.products[1]!r}")

        # Nothing happens if the directory is not updated.
        command.run()

        with self.database as session:
            self.assertEqual(len(session.scalars(select(Product)).all()),
                             product_count)
            receipt = self._get_receipt(session)
            self.assertEqual(receipt.filename, 'receipt.yml')
            self.assertEqual(receipt.updated, updated)

        os.utime('samples', times=(now + 1, now + 1))

        with self.extra_products.open('w', encoding='utf-8') as extra_file:
            extra_file.write('null')

        # Receipt is not changed if the file is not updated.
        # Invalid extra products specification does not change the database.
        command.run()

        with self.database as session:
            self.assertEqual(len(session.scalars(select(Product)).all()),
                             product_count)
            receipt = self._get_receipt(session)
            self.assertEqual(receipt.filename, 'receipt.yml')
            self.assertEqual(receipt.updated, updated)

        with self.extra_products.open('w', encoding='utf-8') as extra_file:
            extra = {
                'shop': 'id',
                'products': [
                    # Updates to existing products (overrides)
                    {
                        'labels': ['weigh'],
                        'description': 'Each product has different proportions'
                    },
                    {
                        'gtin': 1234567890123,
                        'portions': 21,
                        'prices': {
                            'minimum': 0.89,
                            'maximum': 1.09
                        }
                    },
                    {
                        'sku': 'abc123',
                        'prices': [8.00],
                        'brand': 'A Big Bar of Chocolate'
                    },
                    # New product separate from the one before
                    {
                        'bonuses': ['disco'],
                        'type': 'caramel'
                    }
                ]
            }
            yaml.dump(extra, extra_file)

        os.utime('samples/receipt.yml', times=(now + 1, now + 1))
        with patch('rechu.io.receipt.Price', side_effect=self._alter_price):
            command.run()

        with self.database as session:
            products = session.scalars(select(Product)).all()
            self.assertEqual(len(products), product_count + 1)
            self.assertEqual(products[-2].prices[0].value, Price('8.00'))
            self.assertEqual(products[-2].brand, 'A Big Bar of Chocolate')
            self.assertEqual(products[-1].type, 'caramel')
            receipt = self._get_receipt(session)
            self.assertEqual(receipt.filename, 'receipt.yml')
            self.assertNotEqual(receipt.updated, updated)

            # Changes to some receipt items do not cause them to be reordered
            self.assertEqual([product.price for product in receipt.products],
                             [Price('1.99'), Price('5.00'), Price('7.50'),
                              Price('8.00'), Price('2.50'), Price('1.89')])

            self.assertEqual(receipt.products[1].product, products[-1],
                             f"Expected change {receipt.products[1]!r}")

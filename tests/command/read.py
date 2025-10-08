"""
Tests of subcommand to import receipt YAML files.
"""

from datetime import datetime
import os
from pathlib import Path
from typing import Union, final
from unittest.mock import patch
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from typing_extensions import override
import yaml
from rechu.command.read import Read
from rechu.database import Database
from rechu.models import Product, Receipt, Shop
from rechu.types.quantized import Price
from ..database import DatabaseTestCase

@final
class ReadTest(DatabaseTestCase):
    """
    Test reading the YAML files and importing them to the database.
    """

    # Number of products in samples/products-id.yml
    product_count = 3

    # Number of range products in samples/products-id.yml
    range_count = 2

    # Overrides file sorted after samples/products-id.yml
    extra_products = Path("samples/products-id.zzz.yml")

    # Extra products/overrides
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

    min_price = Price('1.00')

    @override
    def setUp(self) -> None:
        super().setUp()
        with Database() as session:
            _ = session.execute(delete(Shop))

    @override
    def tearDown(self) -> None:
        super().tearDown()
        self.extra_products.unlink(missing_ok=True)

    def _get_receipt(self, session: Session) -> Receipt:
        receipt = session.scalar(select(Receipt).limit(1))
        if receipt is None:
            self.fail("Expected receipt to be stored")
        self.assertEqual(receipt.filename, 'receipt.yml')
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

        with self.database as session:
            products = session.scalars(select(Product)).all()
            self.assertEqual(len(products),
                             self.product_count + self.range_count)
            receipt = self._get_receipt(session)
            updated = receipt.updated

            self.assertIsNone(receipt.products[0].product,
                              f"Unexpected match for {receipt.products[0]!r}")
            self.assertEqual(receipt.products[1].product,
                             products[self.product_count - 1].range[1],
                             f"Expected match for {receipt.products[1]!r}")

        # Nothing happens if the directory is not updated.
        command.run()

        with self.database as session:
            self.assertEqual(len(session.scalars(select(Product)).all()),
                             self.product_count + self.range_count)
            receipt = self._get_receipt(session)
            self.assertEqual(receipt.updated, updated)

        os.utime('samples', times=(now + 1, now + 1))

        with self.extra_products.open('w', encoding='utf-8') as extra_file:
            _ = extra_file.write('null')

        # Receipt is not changed if the file is not updated.
        # Invalid extra products specification does not change the database.
        command.run()

        with self.database as session:
            self.assertEqual(len(session.scalars(select(Product)).all()),
                             self.product_count + self.range_count)
            receipt = self._get_receipt(session)
            self.assertEqual(receipt.updated, updated)

        with self.extra_products.open('w', encoding='utf-8') as extra_file:
            yaml.dump(self.extra, extra_file)

        os.utime('samples/receipt.yml', times=(now + 1, now + 1))
        with patch('rechu.io.receipt.Price', side_effect=self._alter_price):
            command.run()

        with self.database as session:
            products = session.scalars(select(Product)
                                       .order_by(Product.id)).all()
            # The updated products overwrite a product range, so just generics
            self.assertEqual(len(products), self.product_count + 1)
            self.assertEqual(products[self.product_count - 1].prices[0].value,
                             Price('8.00'))
            self.assertEqual(products[self.product_count - 1].brand,
                             'A Big Bar of Chocolate')
            self.assertEqual(products[self.product_count].type, 'caramel')
            receipt = self._get_receipt(session)
            self.assertNotEqual(receipt.updated, updated)

            # Changes to some receipt items do not cause them to be reordered
            self.assertEqual([product.price for product in receipt.products],
                             [Price('1.99'), Price('5.00'), Price('7.50'),
                              Price('8.00'), Price('2.50'), Price('1.89')])

            self.assertEqual(receipt.products[1].product,
                             products[self.product_count],
                             f"Expected change {receipt.products[1]!r}")

        self.extra_products.unlink(missing_ok=True)
        command.run()

        with self.database as session:
            products = session.scalars(select(Product)
                                       .order_by(Product.id)).all()
            self.assertEqual(len(products),
                             self.product_count + self.range_count)
            self.assertIsNone(products[self.product_count - 1].brand)
            receipt = self._get_receipt(session)
            self.assertEqual(receipt.products[1].product,
                             products[self.product_count - 1].range[1],
                             f"Expected change {receipt.products[1]!r}")

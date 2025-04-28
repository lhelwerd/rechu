"""
Tests of subcommand to import receipt YAML files.
"""

from datetime import datetime
import os
from pathlib import Path
from sqlalchemy import select
import yaml
from rechu.command.read import Read
from rechu.models import Product, Receipt
from ..database import DatabaseTestCase

class ReadTest(DatabaseTestCase):
    """
    Test reading the YAML files and importing them to the database.
    """

    extra_products = Path("samples/products-id-extra.yml")

    def tearDown(self) -> None:
        super().tearDown()
        self.extra_products.unlink(missing_ok=True)

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
            receipt = session.scalars(select(Receipt)).first()
            if receipt is None:
                self.fail("Expected receipt to be stored")
            self.assertEqual(receipt.filename, 'receipt.yml')
            updated = receipt.updated

        # Nothing happens if the directory is not updated.
        command.run()

        with self.database as session:
            self.assertEqual(len(session.scalars(select(Product)).all()),
                             product_count)
            receipt = session.scalars(select(Receipt)).first()
            if receipt is None:
                self.fail("Expected receipt to be stored")
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
            receipt = session.scalars(select(Receipt)).first()
            if receipt is None:
                self.fail("Expected receipt to be stored")
            self.assertEqual(receipt.filename, 'receipt.yml')
            self.assertEqual(receipt.updated, updated)

        with self.extra_products.open('w', encoding='utf-8') as extra_file:
            extra = {
                'shop': 'id',
                'products': [
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
                        'brand': 'A Bar of Chocolate'
                    }
                ]
            }
            yaml.dump(extra, extra_file)

        os.utime('samples/receipt.yml', times=(now + 1, now + 1))
        command.run()

        with self.database as session:
            self.assertEqual(len(session.scalars(select(Product)).all()),
                             product_count)
            receipt = session.scalars(select(Receipt)).first()
            if receipt is None:
                self.fail("Expected receipt to be stored")
            self.assertEqual(receipt.filename, 'receipt.yml')
            self.assertNotEqual(receipt.updated, updated)

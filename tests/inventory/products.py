"""
Tests for product inventory.
"""

from copy import deepcopy
from itertools import zip_longest
from pathlib import Path
import re
from unittest.mock import patch
from rechu.inventory.products import Products
from rechu.models.product import Product
from rechu.settings import Settings
from tests.database import DatabaseTestCase

class ProductsTest(DatabaseTestCase):
    """
    Tests for inventory of products grouped by their identifying fields.
    """

    extra_products = Path("samples/products-id.zzz.yml")

    def setUp(self) -> None:
        super().setUp()
        self.products = [
            Product(shop='id', sku='abc123'),
            Product(shop='id', sku='def456', category='test', type='foo'),
            Product(shop='other', sku='ghi789', description='Something')
        ]
        self.product_lines = [
            '- {sku: abc123}',
            '- {category: test, type: foo, sku: def456}',
            '- {description: Something, sku: ghi789}'
        ]

    def tearDown(self) -> None:
        super().tearDown()
        self.extra_products.unlink(missing_ok=True)

    def test_get_parts(self) -> None:
        """
        Test retrieving various formatting, selecting and matching parts.
        """

        pattern = r"(^|.*/)samples/products\-(?P<shop>.*)??\.yml$"
        self.assertEqual(Products.get_parts(Settings.get_settings()),
                         ("samples/products-{shop}.yml",
                          "samples/products-*.yml", ("shop",),
                          re.compile(pattern)))

        Settings.clear()

        pattern = r"(^|.*/)p(?P<shop>.*)??(?P<category>.*)??(?P<type>.*)??\.yml$"
        with patch.dict('os.environ',
                        {'RECHU_DATA_PRODUCTS': 'p{shop}{category}{type}.yml'}):
            self.assertEqual(Products.get_parts(Settings.get_settings()),
                             ("p{shop}{category}{type}.yml",
                              "p***.yml", ("shop", "category", "type"),
                              re.compile(pattern)))

    def test_spread(self) -> None:
        """
        Test creating an inventory of products by assigning them to groups.
        """

        inventory = Products.spread(self.products)
        self.assertEqual(list(inventory.keys()), [
            Path('./samples/products-id.yml').resolve(),
            Path('./samples/products-other.yml').resolve()
        ])
        self.assertEqual(list(inventory.values()),
                         [self.products[0:2], self.products[2:3]])

        self.assertEqual(Products.spread([]), {})

    def test_select(self) -> None:
        """
        Test creating an inventory based on products stored in the database.
        """

        with self.database as session:
            self.assertEqual(Products.select(session), {})
        with self.database as session:
            for product in self.products:
                session.add(product)

            session.flush()

            inventory = Products.select(session)
            self.assertEqual(list(inventory.keys()), [
                Path('./samples/products-id.yml').resolve(),
                Path('./samples/products-other.yml').resolve()
            ])
            self.assertEqual(list(inventory.values()),
                             [self.products[0:2], self.products[2:3]])

            other = Products.select(session, selectors=[{'shop': 'other'}])
            self.assertEqual(list(other.keys()), [
                Path('./samples/products-other.yml').resolve()
            ])
            self.assertEqual(list(other.values()), [self.products[2:3]])

    def test_select_no_selectors(self) -> None:
        """
        Test creating an inventory based on products stored in the database
        when there are no replacement fields in the products filename format.
        """

        with patch.dict('os.environ',
                        {'RECHU_DATA_PRODUCTS': 'samples/products.yml'}):
            with self.database as session:
                for product in self.products:
                    session.add(product)

                session.flush()

                inventory = Products.select(session)
                self.assertEqual(list(inventory.keys()), [
                    Path('./samples/products.yml').resolve(),
                ])
                self.assertEqual(list(inventory.values()), [self.products])

                # Event with a shop selector, we do not use it if there are not
                # replacement fields in the products filename format.
                other = Products.select(session, selectors=[{'shop': 'other'}])
                self.assertEqual(list(other.keys()), [
                    Path('./samples/products.yml').resolve()
                ])
                self.assertEqual(list(other.values()), [self.products])

    def test_read(self) -> None:
        """
        Test creating an inventory based on product metadata stored in files.
        """

        inventory = Products.read()
        self.assertEqual(list(inventory.keys()), [
            Path('./samples/products-id.yml').resolve()
        ])
        self.assertEqual(len(list(inventory.values())[0]), 3)

        with self.extra_products.open('w', encoding='utf-8') as extra_file:
            extra_file.write('null')

        # Unreadable files do not lead to a broken inventory.
        extra = Products.read()
        self.assertEqual(list(extra.keys()), [
            Path('./samples/products-id.yml').resolve()
        ])
        self.assertEqual(len(list(extra.values())[0]), 3)

        with self.extra_products.open('w', encoding='utf-8') as extra_file:
            extra_file.write('shop: other\nproducts:\n- brand: Unique')

        # Inventory keys are left as is.
        extra = Products.read()
        self.assertEqual(list(extra.keys()), [
            Path('./samples/products-id.yml').resolve(),
            Path('./samples/products-id.zzz.yml').resolve()
        ])
        self.assertEqual([len(group) for group in extra.values()], [3, 1])
        self.assertEqual(list(extra.values())[1][0].brand, 'Unique')

    def test_get_writers(self) -> None:
        """
        Test obtain writers for each inventory file of products.
        """

        writers = [writer.path for writer in Products.read().get_writers()]
        self.assertEqual(writers, [Path('./samples/products-id.yml').resolve()])

        with self.extra_products.open('w', encoding='utf-8') as extra_file:
            extra_file.write('shop: other\nproducts:\n- brand: Unique')

        writers = [writer.path for writer in Products.read().get_writers()]
        self.assertEqual(writers, [
            Path('./samples/products-id.yml').resolve(),
            Path('./samples/products-id.zzz.yml').resolve()
        ])

    def test_write(self) -> None:
        """
        Test writing an inventory of products to files.
        """

        # No op does not change current inventories.
        Products().write()
        self.assertFalse(self.extra_products.exists())

        for product in self.products:
            product.shop = 'id.zzz'
        Products({Path('./samples/products-id.zzz.yml'): self.products}).write()
        self.assertTrue(self.extra_products.exists())
        with self.extra_products.open('r', encoding='utf-8') as extra_file:
            expected_lines = ['shop: id.zzz', 'products:'] + self.product_lines
            for i, (line, expected) in enumerate(zip_longest(extra_file,
                                                             expected_lines)):
                with self.subTest(index=i):
                    self.assertEqual(line.rstrip() if line is not None else "",
                                     expected)

    def test_merge_update(self) -> None:
        """
        Test finding groups of products that are added or updated in another
        inventory.
        """

        inventory = Products.spread(self.products)
        self.assertEqual(inventory.merge_update(inventory), {})

        products = deepcopy(self.products)
        products[1].type = 'bar'
        products.append(Product(shop='other', gtin=1234567890123))
        other = Products.spread(products)

        updated = inventory.merge_update(other)
        self.assertEqual(list(updated.keys()), [
            Path('./samples/products-id.yml').resolve(),
            Path('./samples/products-other.yml').resolve()
        ])
        self.assertEqual(list(updated.values())[0], self.products[0:2])
        self.assertEqual(len(list(updated.values())[1]), 2)
        self.assertEqual(list(updated.values())[1][0], self.products[2])
        self.assertEqual(list(updated.values())[1][1].gtin, 1234567890123)
        self.assertEqual(list(inventory.values())[0], self.products[0:2])
        self.assertEqual(len(list(inventory.values())[1]), 2)
        self.assertEqual(list(inventory.values())[1][0], self.products[2])
        self.assertEqual(list(inventory.values())[1][1].gtin, 1234567890123)

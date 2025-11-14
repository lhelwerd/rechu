"""
Tests for product inventory.
"""

import re
from copy import deepcopy
from itertools import zip_longest
from pathlib import Path
from typing import final

from typing_extensions import override

from rechu.inventory.base import Inventory
from rechu.inventory.products import Products
from rechu.matcher.product import MapKey
from rechu.models import Product, Shop
from rechu.settings import Settings

from ..database import DatabaseTestCase
from ..settings import patch_settings

_Check = dict[str, str | int]


@final
class ProductsTest(DatabaseTestCase):
    """
    Tests for inventory of products grouped by their identifying fields.
    """

    extra_products = Path("samples/products-id.zzz.yml")

    @override
    def setUp(self) -> None:
        super().setUp()
        self.products = [
            Product(shop="id", sku="abc123"),
            Product(shop="id", sku="def456", category="test", type="foo"),
            Product(shop="other", sku="ghi789", description="Something"),
        ]
        self.product_lines = [
            "- {sku: abc123}",
            "- {category: test, type: foo, sku: def456}",
            "- {description: Something, sku: ghi789}",
        ]

        # Inventories for merge_update tests
        self.inventory = Products.spread(deepcopy(self.products))
        products = deepcopy(self.products)
        products[1].type = "bar"
        self.portions = Product(shop="other", gtin=1234567890123, portions=42)
        products.append(self.portions)
        self.other = Products.spread(products)

    @override
    def tearDown(self) -> None:
        super().tearDown()
        self.extra_products.unlink(missing_ok=True)

    def test_get_parts(self) -> None:
        """
        Test retrieving various formatting, selecting and matching parts.
        """

        pattern = r"(^|.*/)samples/products\-(?P<shop>.*)??\.yml$"
        self.assertEqual(
            Products.get_parts(Settings.get_settings()),
            (
                "samples/products-{shop}.yml",
                "samples/products-*.yml",
                ("shop",),
                re.compile(pattern),
            ),
        )

        Settings.clear()

        pattern = (
            r"(^|.*/)p(?P<shop>.*)??(?P<category>.*)??(?P<type>.*)??\.yml$"
        )
        with patch_settings(
            {"RECHU_DATA_PRODUCTS": "p{shop}{category}{type}.yml"}
        ):
            self.assertEqual(
                Products.get_parts(Settings.get_settings()),
                (
                    "p{shop}{category}{type}.yml",
                    "p***.yml",
                    ("shop", "category", "type"),
                    re.compile(pattern),
                ),
            )

    def test_spread(self) -> None:
        """
        Test creating an inventory of products by assigning them to groups.
        """

        inventory = Products.spread(self.products)
        self.assertEqual(
            list(inventory.keys()),
            [
                Path("./samples/products-id.yml").resolve(),
                Path("./samples/products-other.yml").resolve(),
            ],
        )
        self.assertEqual(
            list(inventory.values()), [self.products[0:2], self.products[2:3]]
        )

        self.assertEqual(Products.spread([]), {})

    def test_select(self) -> None:
        """
        Test creating an inventory based on products stored in the database.
        """

        with self.database as session:
            self.assertEqual(Products.select(session), {})
        with self.database as session:
            session.add(Shop(key="other"))
            session.flush()

            for product in self.products:
                session.add(product)

            session.flush()

            inventory = Products.select(session)
            self.assertEqual(
                list(inventory.keys()),
                [
                    Path("./samples/products-id.yml").resolve(),
                    Path("./samples/products-other.yml").resolve(),
                ],
            )
            self.assertEqual(
                list(inventory.values()),
                [self.products[0:2], self.products[2:3]],
            )

            other = Products.select(session, selectors=[{"shop": "other"}])
            self.assertEqual(
                list(other.keys()),
                [Path("./samples/products-other.yml").resolve()],
            )
            self.assertEqual(list(other.values()), [self.products[2:3]])

    def test_select_no_selectors(self) -> None:
        """
        Test creating an inventory based on products stored in the database
        when there are no replacement fields in the products filename format.
        """

        with patch_settings({"RECHU_DATA_PRODUCTS": "samples/products.yml"}):
            with self.database as session:
                session.add(Shop(key="other"))
                session.flush()

                for product in self.products:
                    session.add(product)

                session.flush()

                inventory = Products.select(session)
                self.assertEqual(
                    list(inventory.keys()),
                    [
                        Path("./samples/products.yml").resolve(),
                    ],
                )
                self.assertEqual(list(inventory.values()), [self.products])

                # Event with a shop selector, we do not use it if there are not
                # replacement fields in the products filename format.
                other = Products.select(session, selectors=[{"shop": "other"}])
                self.assertEqual(
                    list(other.keys()),
                    [Path("./samples/products.yml").resolve()],
                )
                self.assertEqual(list(other.values()), [self.products])

    def test_read(self) -> None:
        """
        Test creating an inventory based on product metadata stored in files.
        """

        inventory = Products.read()
        self.assertEqual(
            list(inventory.keys()),
            [Path("./samples/products-id.yml").resolve()],
        )
        self.assertEqual(len(next(iter(inventory.values()))), 3)

        with self.extra_products.open("w", encoding="utf-8") as extra_file:
            _ = extra_file.write("null")

        # Unreadable files do not lead to a broken inventory.
        extra = Products.read()
        self.assertEqual(
            list(extra.keys()), [Path("./samples/products-id.yml").resolve()]
        )
        self.assertEqual(len(next(iter(extra.values()))), 3)

        with self.extra_products.open("w", encoding="utf-8") as extra_file:
            _ = extra_file.write("shop: other\nproducts:\n- brand: Unique")

        # Inventory keys are left as is.
        extra = Products.read()
        self.assertEqual(
            list(extra.keys()),
            [
                Path("./samples/products-id.yml").resolve(),
                Path("./samples/products-id.zzz.yml").resolve(),
            ],
        )
        self.assertEqual([len(group) for group in extra.values()], [3, 1])
        self.assertEqual(list(extra.values())[1][0].brand, "Unique")

    def test_get_writers(self) -> None:
        """
        Test obtaining writers for each inventory file of products.
        """

        writers = [writer.path for writer in Products.read().get_writers()]
        self.assertEqual(writers, [Path("./samples/products-id.yml").resolve()])

        with self.extra_products.open("w", encoding="utf-8") as extra_file:
            _ = extra_file.write("shop: other\nproducts:\n- brand: Unique")

        writers = [writer.path for writer in Products.read().get_writers()]
        self.assertEqual(
            writers,
            [
                Path("./samples/products-id.yml").resolve(),
                Path("./samples/products-id.zzz.yml").resolve(),
            ],
        )

    def test_write(self) -> None:
        """
        Test writing an inventory of products to files.
        """

        # No op does not change current inventories.
        Products().write()
        self.assertFalse(self.extra_products.exists())

        for product in self.products:
            product.shop = "id.zzz"
        Products({Path("./samples/products-id.zzz.yml"): self.products}).write()
        self.assertTrue(self.extra_products.exists())
        with self.extra_products.open("r", encoding="utf-8") as extra_file:
            expected_lines = ["shop: id.zzz", "products:", *self.product_lines]
            for i, (line, expected) in enumerate(
                zip_longest(extra_file, expected_lines)
            ):
                with self.subTest(index=i):
                    self.assertEqual(
                        line.rstrip() if line is not None else "", expected
                    )

    def _check_inventory(
        self,
        inventory: Inventory[Product],
        expected: dict[str, tuple[_Check, ...]],
    ) -> None:
        for pair, expected_pair in zip_longest(
            inventory.items(), expected.items()
        ):
            if pair is None:
                self.fail(f"Missing path {expected_pair[0]} in inventory")
            if expected_pair is None:
                self.fail(f"Unexpected path {pair[0]} in inventory")
            path, products = pair
            expected_path, expected_data = expected_pair
            self.assertEqual(path, Path(expected_path).resolve())
            for index, (product, data) in enumerate(
                zip_longest(products, expected_data)
            ):
                with self.subTest(index=index):
                    if product is None:
                        self.fail(f"Missing products {data} in inventory")
                    if data is None:
                        self.fail(f"Unexpected {product!r} in inventory")
                    for key, value in data.items():
                        self.assertEqual(getattr(product, key), value)

    def test_merge_update(self) -> None:
        """
        Test finding groups of products that are added or updated in another
        inventory.
        """

        self.assertEqual(self.inventory.merge_update(self.inventory), {})

        updated = self.inventory.merge_update(self.other)
        self._check_inventory(
            updated,
            {
                "./samples/products-id.yml": (
                    {"sku": "abc123"},
                    {"sku": "def456", "type": "bar"},
                ),
                "./samples/products-other.yml": (
                    {"sku": "ghi789"},
                    {"gtin": 1234567890123, "portions": 42},
                ),
            },
        )
        # The inventory itself was also updated.
        self._check_inventory(
            self.inventory,
            {
                "./samples/products-id.yml": (
                    {"sku": "abc123"},
                    {"sku": "def456", "type": "bar"},
                ),
                "./samples/products-other.yml": (
                    {"sku": "ghi789"},
                    {"gtin": 1234567890123, "portions": 42},
                ),
            },
        )

    def test_merge_update_partial(self) -> None:
        """
        Test finding groups of products that are added or updated in another
        inventory, which does not hold all the original products.
        """

        updated = self.inventory.merge_update(
            Products(
                {
                    path: items[1:] if index >= 1 else items[:-1]
                    for index, (path, items) in enumerate(self.other.items())
                }
            )
        )
        # Only updated paths are included, holding the full updated inventory.
        self._check_inventory(
            updated,
            {
                "./samples/products-other.yml": (
                    {"sku": "ghi789"},
                    {"gtin": 1234567890123, "portions": 42},
                )
            },
        )
        # The inventory itself was also updated with the new addition.
        self._check_inventory(
            self.inventory,
            {
                "./samples/products-id.yml": (
                    {"sku": "abc123"},
                    {"sku": "def456", "type": "foo"},
                ),
                "./samples/products-other.yml": (
                    {"sku": "ghi789"},
                    {"gtin": 1234567890123, "portions": 42},
                ),
            },
        )

    def test_merge_update_no_update(self) -> None:
        """
        Test finding groups of products that are added or changed in another
        inventory without adding them to the current inventory.
        """

        self.assertEqual(
            self.inventory.merge_update(self.inventory, update=False), {}
        )

        updated = self.inventory.merge_update(self.other, update=False)
        self._check_inventory(
            updated,
            {
                "./samples/products-id.yml": (
                    {"sku": "abc123"},
                    {"sku": "def456", "type": "bar"},
                ),
                "./samples/products-other.yml": (
                    {"sku": "ghi789"},
                    {"gtin": 1234567890123, "portions": 42},
                ),
            },
        )
        # The inventory itself was not updated.
        self._check_inventory(
            self.inventory,
            {
                "./samples/products-id.yml": (
                    {"sku": "abc123"},
                    {"sku": "def456", "type": "foo"},
                ),
                "./samples/products-other.yml": ({"sku": "ghi789"},),
            },
        )

    def test_merge_update_only_new(self) -> None:
        """
        Test finding groups of products that are added in another inventory.
        """

        self.assertEqual(
            self.inventory.merge_update(self.inventory, only_new=True), {}
        )

        new = self.inventory.merge_update(self.other, only_new=True)
        self._check_inventory(
            new,
            {
                "./samples/products-other.yml": (
                    {"gtin": 1234567890123, "portions": 42},
                )
            },
        )

    def test_find(self) -> None:
        """
        Test finding metadata for a product identified by a unique key.
        """

        product = self.inventory.find((MapKey.MAP_SKU, ("id", "abc123")))
        self.assertFalse(product.merge(self.products[0]))
        inv = self.inventory.find((MapKey.MAP_GTIN, ("inv", 9876543210321)))
        self.assertEqual(inv.shop, "inv")
        self.assertEqual(inv.gtin, 9876543210321)

        _ = self.inventory.merge_update(self.other)
        key = (MapKey.MAP_GTIN, ("other", 1234567890123))
        self.assertIsNot(self.inventory.find(key), self.portions)
        self.assertIs(self.inventory.find(key, update_map=True), self.portions)

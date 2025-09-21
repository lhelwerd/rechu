"""
Tests for shop inventory.
"""

from copy import deepcopy
from itertools import zip_longest
from pathlib import Path
from unittest.mock import patch
from sqlalchemy import delete
from rechu.inventory import Inventory
from rechu.inventory.shops import Shops
from rechu.models.shop import Shop
from rechu.settings import Settings
from ..database import DatabaseTestCase

class ShopsTest(DatabaseTestCase):
    """
    Tests for inventory of shops.
    """

    other_shops = Path("samples/shops.zzz.yml")

    def setUp(self) -> None:
        super().setUp()
        self.shops = [
            Shop(key='id', name='Generic', website='https://example.com'),
            Shop(key='inv', name='Inventory')
        ]
        self.lines = [
            "- {key: id, name: Generic, website: 'https://example.com'}",
            "- {key: inv, name: Inventory}"
        ]

        self.inventory = Shops.spread(deepcopy(self.shops))
        shops = deepcopy(self.shops)
        shops[1].name = 'Invalid'
        self.other = Shop(key='other', name='Competitor')
        self.extra = Shops.spread(shops + [self.other])

    def tearDown(self) -> None:
        super().tearDown()
        self.other_shops.unlink(missing_ok=True)

    def test_spread(self) -> None:
        """
        Test creating an inventory of shops.
        """

        inventory = Shops.spread(self.shops)
        path = Path('./samples/shops.yml').resolve()
        self.assertEqual(list(inventory.keys()), [path])
        self.assertEqual(list(inventory.values()), [self.shops])

        empty = Shops.spread([])
        self.assertEqual(list(empty.keys()), [path])
        self.assertEqual(list(empty.values()), [[]])

    def test_select(self) -> None:
        """
        Test creating an inventory based on shops stored in the database.
        """

        path = Path('./samples/shops.yml').resolve()
        with self.database as session:
            session.execute(delete(Shop))
            session.flush()
            empty = Shops.select(session)
            self.assertEqual(list(empty.keys()), [path])
            self.assertEqual(list(empty.values()), [[]])

        with self.database as session:
            for shop in self.shops:
                session.add(shop)

            session.flush()

            inventory = Shops.select(session)
            self.assertEqual(list(inventory.keys()), [path])
            self.assertEqual(list(inventory.values()), [self.shops])

            with self.assertRaises(ValueError):
                Shops.select(session, selectors=[{'name': 'Inventory'}])

    def test_read(self) -> None:
        """
        Test creating an inventory based on shop metadata stored in files.
        """

        inventory = Shops.read()
        self.assertEqual(list(inventory.keys()),
                         [Path('./samples/shops.yml').resolve()])
        self.assertEqual(len(list(inventory.values())[0]), 2)

        Settings.clear()

        invalid_path = Path("samples/invalid-shops/key.yml")
        with patch.dict('os.environ', {"RECHU_DATA_SHOPS": str(invalid_path)}):
            invalid = Shops.read()
            self.assertEqual(list(invalid.keys()), [invalid_path.resolve()])
            self.assertEqual(list(invalid.values()), [[]])

        Settings.clear()

        missing_path = Path("samples/missing-shops.yml")
        with patch.dict('os.environ', {"RECHU_DATA_SHOPS": str(missing_path)}):
            invalid = Shops.read()
            self.assertEqual(list(invalid.keys()), [missing_path.resolve()])
            self.assertEqual(list(invalid.values()), [[]])

    def test_get_writers(self) -> None:
        """
        Test obtaining writers for the inventory file of shops.
        """

        writers = [writer.path for writer in Shops.read().get_writers()]
        self.assertEqual(writers, [Path('./samples/shops.yml').resolve()])

    def test_write(self) -> None:
        """
        Test writing an inventory of shops to the file.
        """

        with patch.dict('os.environ',
                        {"RECHU_DATA_SHOPS": str(self.other_shops)}):
            # Empty inventory write does not change current inventory file.
            Shops().write()
            self.assertFalse(self.other_shops.exists())

            Shops({self.other_shops.resolve(): self.shops}).write()
            self.assertTrue(self.other_shops.exists())

            with self.other_shops.open('r', encoding='utf-8') as other_file:
                for i, (line, expected) in enumerate(zip_longest(other_file,
                                                                 self.lines)):
                    with self.subTest(index=i):
                        self.assertEqual(line.rstrip()
                                         if line is not None else "",
                                         expected)

    def _check_inventory(self, inventory: Inventory[Shop],
                         expected: tuple[dict[str, str], ...]) -> None:
        path = Path("./samples/shops.yml").resolve()
        if path not in inventory:
            self.fail(f"Missing path {path} in inventory")
        if len(inventory) > 1:
            self.fail(f"Unexpected paths in inventory: {inventory!r}")

        for index, (shop, data) in enumerate(zip_longest(inventory[path],
                                                         expected)):
            with self.subTest(index=index):
                if shop is None:
                    self.fail(f"Missing shop {data} in inventory")
                if data is None:
                    self.fail(f"Unexpected {shop!r} in inventory")
                for key, value in data.items():
                    self.assertEqual(getattr(shop, key), value)

    def test_merge_update(self) -> None:
        """
        Test finding shops that are added or updated in another inventory.
        """

        self.assertEqual(self.inventory.merge_update(self.inventory), {})

        updated = self.inventory.merge_update(self.extra)
        self._check_inventory(updated, (
            {'key': 'id', 'name': 'Generic', 'website': 'https://example.com'},
            {'key': 'inv', 'name': 'Invalid'},
            {'key': 'other', 'name': 'Competitor'}
        ))

        # The inventory itself was also updated.
        self._check_inventory(self.inventory, (
            {'key': 'id', 'name': 'Generic', 'website': 'https://example.com'},
            {'key': 'inv', 'name': 'Invalid'},
            {'key': 'other', 'name': 'Competitor'}
        ))

    def test_merge_update_partial(self) -> None:
        """
        Test finding shops that are added or updated in another inventory,
        which does not hold all the original shops.
        """

        updated = self.inventory.merge_update(Shops.spread([self.other]))
        # The updated path holds the full updated inventory.
        self._check_inventory(updated, (
            {'key': 'id', 'name': 'Generic', 'website': 'https://example.com'},
            {'key': 'inv', 'name': 'Inventory'},
            {'key': 'other', 'name': 'Competitor'}
        ))

        # The inventory itself was also updated with the new addition.
        self._check_inventory(self.inventory, (
            {'key': 'id', 'name': 'Generic', 'website': 'https://example.com'},
            {'key': 'inv', 'name': 'Inventory'},
            {'key': 'other', 'name': 'Competitor'}
        ))

    def test_merge_update_no_update(self) -> None:
        """
        Test finding shops that are added or updated in another inventory
        without adding them to the current inventory.
        """

        self.assertEqual(self.inventory.merge_update(self.inventory,
                                                     update=False), {})

        updated = self.inventory.merge_update(self.extra, update=False)
        self._check_inventory(updated, (
            {'key': 'id', 'name': 'Generic', 'website': 'https://example.com'},
            {'key': 'inv', 'name': 'Invalid'},
            {'key': 'other', 'name': 'Competitor'}
        ))

        # The inventory itself was not updated.
        self._check_inventory(self.inventory, (
            {'key': 'id', 'name': 'Generic', 'website': 'https://example.com'},
            {'key': 'inv', 'name': 'Inventory'}
        ))

    def test_merge_update_only_new(self) -> None:
        """
        Test finding shops that are added in another inventory.
        """

        self.assertEqual(self.inventory.merge_update(self.inventory,
                                                     only_new=True), {})

        new = self.inventory.merge_update(self.extra, only_new=True)
        self._check_inventory(new, (
            {'key': 'other', 'name': 'Competitor'},
        ))

    def test_find(self) -> None:
        """
        Test finding metadata for a shop identified by a unique key.
        """

        shop = self.inventory.find("id")
        self.assertFalse(shop.merge(self.shops[0]))
        inv = self.inventory.find("inv")
        self.assertEqual(inv.key, "inv")
        self.assertEqual(inv.name, "Inventory")

        self.inventory.merge_update(self.extra)
        found = self.inventory.find("other")
        self.assertIsNot(found, self.other)
        self.assertEqual(found.key, "other")
        self.assertIsNone(found.name)

        self.assertIs(self.inventory.find("other", update_map=True),
                      self.other)

        with self.assertRaisesRegex(TypeError,
                                    "Cannot construct empty Shop metadata"):
            self.inventory.find(("some", "other", "key"))

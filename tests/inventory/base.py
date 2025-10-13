"""
Tests for abstract bag of models grouped by file that share common properties.
"""

from collections.abc import Iterable
from pathlib import Path
from typing import Optional, final
import unittest
from unittest.mock import MagicMock
from sqlalchemy.orm import Session
from typing_extensions import override
from rechu.inventory.base import Inventory, Selectors
from ..models.base import TestEntity


@final
class TestInventory(Inventory[TestEntity], dict[Path, list[TestEntity]]):
    # pylint: disable=abstract-method
    """
    Inventory that stores test entities.
    """

    __getitem__ = dict[Path, list[TestEntity]].__getitem__
    __iter__ = dict[Path, list[TestEntity]].__iter__
    __len__ = dict[Path, list[TestEntity]].__len__

    @classmethod
    @override
    def spread(cls, models: Iterable[TestEntity]) -> Inventory[TestEntity]:
        return super().spread(models)

    @classmethod
    @override
    def select(
        cls, session: Session, selectors: Optional[Selectors] = None
    ) -> Inventory[TestEntity]:
        return super().select(session, selectors)

    @classmethod
    @override
    def read(cls) -> Inventory[TestEntity]:
        return super().read()

    get_writers = Inventory[TestEntity].get_writers
    merge_update = Inventory[TestEntity].merge_update
    find = Inventory[TestEntity].find


# mypy: disable-error-code="abstract"
# pyright: reportAbstractUsage=false
@final
class InventoryTest(unittest.TestCase):
    """
    Tests for inventory of model type grouped by characteristics.
    """

    @override
    def setUp(self) -> None:
        self.inventory = TestInventory()

    def test_spread(self) -> None:
        """
        Test creating an inventory based on models by assigning them to groups.
        """

        with self.assertRaises(NotImplementedError):
            self.assertIsNone(
                TestInventory.spread([TestEntity(id=1), TestEntity(id=2)])
            )

    def test_select(self) -> None:
        """
        Test creating an inventory based on models stored in the database.
        """

        with self.assertRaises(NotImplementedError):
            self.assertIsNone(TestInventory.select(MagicMock()))

    def test_read(self) -> None:
        """
        Test creating an inventory based on models stored in files.
        """

        with self.assertRaises(NotImplementedError):
            self.assertIsNone(TestInventory.read())

    def test_get_writers(self) -> None:
        """
        Test obtaining writers for each inventory file.
        """

        with self.assertRaises(NotImplementedError):
            self.inventory.write()

    def test_write(self) -> None:
        """
        Test writing an inventory to files.
        """

        with self.assertRaises(NotImplementedError):
            self.inventory.write()

    def test_merge_update(self) -> None:
        """
        Test finding groups with models that are added or updated in another
        inventory.
        """

        with self.assertRaises(NotImplementedError):
            self.assertIsNone(self.inventory.merge_update(MagicMock()))

    def test_find(self) -> None:
        """
        Test finding metadata for a model identified by a unique key.
        """

        with self.assertRaises(NotImplementedError):
            self.assertIsNone(self.inventory.find(""))

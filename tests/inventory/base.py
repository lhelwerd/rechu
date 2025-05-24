"""
Tests for abstract bag of models grouped by file that share common properties.
"""

from abc import ABCMeta
import unittest
from unittest.mock import MagicMock
from rechu.inventory.base import Inventory
from tests.models.base import TestEntity

class TestInventory(dict, Inventory[TestEntity], metaclass=ABCMeta):
    """
    Inventory that stores test entities.
    """

class InventoryTest(unittest.TestCase):
    """
    Tests for inventory of model type grouped by characteristics.
    """

    def test_spread(self) -> None:
        """
        Test creating an inventory based on models by assigning them to groups.
        """

        with self.assertRaises(NotImplementedError):
            Inventory.spread([TestEntity(id=1), TestEntity(id=2)])

    def test_select(self) -> None:
        """
        Test creating an inventory based on models stored in the database.
        """

        with self.assertRaises(NotImplementedError):
            Inventory.select(MagicMock())

    def test_read(self) -> None:
        """
        Test creating an inventory based on models stored in files.
        """

        with self.assertRaises(NotImplementedError):
            Inventory.read()

    def test_merge_update(self) -> None:
        """
        Test finding groups with models that are added or updated in another
        inventory.
        """

        with self.assertRaises(NotImplementedError):
            TestInventory().merge_update(MagicMock())

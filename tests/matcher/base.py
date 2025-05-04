"""
Tests for database entity matching methods.
"""

from pathlib import Path
import unittest
from unittest.mock import MagicMock
from rechu.matcher.base import Matcher
from tests.inventory.base import TestInventory
from tests.models.base import TestEntity

class MatcherTest(unittest.TestCase):
    """
    Test for generic item candidate model matcher.
    """

    def test_find_candidates(self) -> None:
        """
        Test detecting candidate models.
        """

        with self.assertRaises(NotImplementedError):
            Matcher().find_candidates(MagicMock())

    def test_filter_duplicate_candidates(self) -> None:
        """
        Test detecting if item models were matched against multiple candidates.
        """

        matcher: Matcher[TestEntity, TestEntity] = Matcher()
        one = TestEntity(id=1)
        two = TestEntity(id=2)
        three = TestEntity(id=3)
        four = TestEntity(id=4)
        self.assertEqual(list(matcher.filter_duplicate_candidates([])), [])
        filtered = matcher.filter_duplicate_candidates([(two, one),
                                                        (three, one),
                                                        (four, two)])
        self.assertEqual(list(filtered), [(four, two)])

    def test_match(self) -> None:
        """
        Test checking if a candidate model matches an item model.
        """

        with self.assertRaises(NotImplementedError):
            Matcher().match(MagicMock(), MagicMock())

    def test_load_map(self) -> None:
        """
        Test creating a mapping of unique keys of candidate models.
        """

        # No exception raised
        Matcher().load_map(MagicMock())

    def test_fill_map(self) -> None:
        """
        Test updating a mapping of unique keys of candidate models from a filled
        inventory.
        """

        # No exceptions raised
        matcher: Matcher[TestEntity, TestEntity] = Matcher()
        inventories: list[TestInventory] = [
            TestInventory({Path('.'): [TestEntity(id=1), TestEntity(id=2)]}),
            TestInventory({
                Path('../samples'): [],
                Path('..'): [TestInventory(id=3)]
            }),
            TestInventory({})
        ]
        for inventory in inventories:
            matcher.fill_map(inventory)

    def test_add_map(self) -> None:
        """
        Test manually adding a candidate model to a mapping of unique keys.
        """

        self.assertFalse(Matcher().add_map(MagicMock()))

    def test_discard_map(self) -> None:
        """
        Test removing a candidate model from a mapping of unique keys.
        """

        self.assertFalse(Matcher().discard_map(MagicMock()))

    def test_check_map(self) -> None:
        """
        Test retrieving a candidate model which has one or more unique keys.
        """

        self.assertIsNone(Matcher().check_map(MagicMock()))

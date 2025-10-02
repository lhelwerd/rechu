"""
Tests for database entity matching methods.
"""

from pathlib import Path
import unittest
from unittest.mock import MagicMock
from rechu.matcher.base import Matcher
from .. import concrete
from ..inventory.base import TestInventory
from ..models.base import TestEntity

class TestMatcher(Matcher[TestEntity, TestEntity]):
    """
    Test item candidate model matcher.
    """

    find_candidates = concrete(Matcher[TestEntity, TestEntity].find_candidates)
    match = concrete(Matcher[TestEntity, TestEntity].match)

# mypy: disable-error-code="abstract"
class MatcherTest(unittest.TestCase):
    """
    Test for generic item candidate model matcher.
    """

    def setUp(self) -> None:
        self.matcher = TestMatcher()

    def test_find_candidates(self) -> None:
        """
        Test detecting candidate models.
        """

        with self.assertRaises(NotImplementedError):
            self.matcher.find_candidates(MagicMock())

    def test_filter_duplicate_candidates(self) -> None:
        """
        Test detecting if item models were matched against multiple candidates.
        """

        one = TestEntity(id=1)
        two = TestEntity(id=2)
        three = TestEntity(id=3)
        four = TestEntity(id=4)
        self.assertEqual(list(self.matcher.filter_duplicate_candidates([])),
                         [])
        filtered = self.matcher.filter_duplicate_candidates([(two, one),
                                                             (three, one),
                                                             (four, two)])
        self.assertEqual(list(filtered), [(four, two)])

    def test_select_duplicate(self) -> None:
        """
        Test deremining which candiate model should be matched against an item.
        """

        one = TestEntity(id=1)
        two = TestEntity(id=2)
        self.assertIsNone(self.matcher.select_duplicate(one, two))
        self.assertIs(self.matcher.select_duplicate(one, one), one)

    def test_match(self) -> None:
        """
        Test checking if a candidate model matches an item model.
        """

        with self.assertRaises(NotImplementedError):
            self.matcher.match(MagicMock(), MagicMock())

    def test_load_map(self) -> None:
        """
        Test creating a mapping of unique keys of candidate models.
        """

        # No exception raised
        self.matcher.load_map(MagicMock())

    def test_clear_map(self) -> None:
        """
        Test clearing the mapping of unique keys.
        """

        # No exception raised
        self.matcher.clear_map()

    def test_fill_map(self) -> None:
        """
        Test updating a mapping of unique keys of candidate models from a filled
        inventory.
        """

        # No exceptions raised
        inventories: list[TestInventory] = [
            TestInventory({ # pyright: ignore[reportAbstractUsage]
                Path('.'): [TestEntity(id=1), TestEntity(id=2)]
            }),
            TestInventory({ # pyright: ignore[reportAbstractUsage]
                Path('../samples'): [],
                Path('..'): [TestEntity(id=3)]
            }),
            TestInventory({}) # pyright: ignore[reportAbstractUsage]
        ]
        for inventory in inventories:
            self.matcher.fill_map(inventory)

    def test_add_map(self) -> None:
        """
        Test manually adding a candidate model to a mapping of unique keys.
        """

        self.assertFalse(self.matcher.add_map(MagicMock()))

    def test_discard_map(self) -> None:
        """
        Test removing a candidate model from a mapping of unique keys.
        """

        self.assertFalse(self.matcher.discard_map(MagicMock()))

    def test_check_map(self) -> None:
        """
        Test retrieving a candidate model which has one or more unique keys.
        """

        self.assertIsNone(self.matcher.check_map(MagicMock()))

    def test_find_map(self) -> None:
        """
        Test finding a candidate in the filled map based on a hash key.
        """

        with self.assertRaises(TypeError):
            self.matcher.find_map("")

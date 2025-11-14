"""
Tests for database entity matching methods.
"""

import unittest
from pathlib import Path
from typing import final
from unittest.mock import MagicMock

from typing_extensions import override

from rechu.matcher.base import Matcher

from .. import concrete
from ..inventory.base import TestInventory
from ..models.base import TestEntity


@final
class TestMatcher(Matcher[TestEntity, TestEntity]):
    """
    Test item candidate model matcher.
    """

    find_candidates = concrete(Matcher[TestEntity, TestEntity].find_candidates)
    match = concrete(Matcher[TestEntity, TestEntity].match)
    get_keys = concrete(Matcher[TestEntity, TestEntity].get_keys)
    select_candidates = concrete(
        Matcher[TestEntity, TestEntity].select_candidates
    )


# mypy: disable-error-code="abstract"
class MatcherTest(unittest.TestCase):
    """
    Test for generic item candidate model matcher.
    """

    @override
    def setUp(self) -> None:
        super().setUp()
        self.matcher: Matcher[TestEntity, TestEntity] = TestMatcher()

    def test_find_candidates(self) -> None:
        """
        Test detecting candidate models.
        """

        with self.assertRaises(NotImplementedError):
            self.assertIsNone(self.matcher.find_candidates(MagicMock()))

    def test_filter_duplicate_candidates(self) -> None:
        """
        Test detecting if item models were matched against multiple candidates.
        """

        one = TestEntity(id=1)
        two = TestEntity(id=2)
        three = TestEntity(id=3)
        four = TestEntity(id=4)
        self.assertEqual(list(self.matcher.filter_duplicate_candidates([])), [])
        filtered = self.matcher.filter_duplicate_candidates(
            [(two, one), (three, one), (four, two)]
        )
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
            self.assertFalse(self.matcher.match(MagicMock(), MagicMock()))

    def test_get_keys(self) -> None:
        """
        Test generating a number of identifying keys for candidate models.
        """

        with self.assertRaises(NotImplementedError):
            self.assertIsNone(self.matcher.get_keys(MagicMock()))

    def test_select_candidates(self) -> None:
        """
        Test retrieving candidate models from the database.
        """

        with self.assertRaises(NotImplementedError):
            self.assertIsNone(self.matcher.select_candidates(MagicMock()))

    def test_load_map(self) -> None:
        """
        Test creating a mapping of unique keys of candidate models.
        """

        with self.assertRaises(NotImplementedError):
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

        with self.assertRaises(NotImplementedError):
            inventories: list[TestInventory] = [
                TestInventory(
                    {Path.cwd(): [TestEntity(id=1), TestEntity(id=2)]}
                ),
                TestInventory(
                    {
                        Path("../samples").resolve(): [],
                        Path("..").resolve(): [TestEntity(id=3)],
                    }
                ),
                TestInventory({}),
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

        self.matcher.clear_map()
        with self.assertRaises(NotImplementedError):
            self.assertFalse(self.matcher.discard_map(MagicMock()))

    def test_check_map(self) -> None:
        """
        Test retrieving a candidate model which has one or more unique keys.
        """

        self.assertIsNone(self.matcher.check_map(MagicMock()))

        self.matcher.clear_map()
        with self.assertRaises(NotImplementedError):
            self.assertIsNone(self.matcher.check_map(MagicMock()))

    def test_find_map(self) -> None:
        """
        Test finding a candidate in the filled map based on a hash key.
        """

        with self.assertRaises(TypeError):
            self.assertIsNone(self.matcher.find_map(""))

        self.matcher.clear_map()
        with self.assertRaises(TypeError):
            self.assertIsNone(self.matcher.find_map("missing"))

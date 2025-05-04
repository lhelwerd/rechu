"""
Tests for base model for receipt cataloging.
"""

from decimal import Decimal
from typing import cast
import unittest
from sqlalchemy import ForeignKey, Table
from sqlalchemy.orm import Mapped, mapped_column
from rechu.models.base import Base, Price

class TestEntity(Base): # pylint: disable=too-few-public-methods
    """
    Test entity.
    """

    __tablename__ = "test"

    id: Mapped[int] = mapped_column(primary_key=True)
    other: Mapped[int] = mapped_column(ForeignKey('test.id'))

class PriceTest(unittest.TestCase):
    """
    Tests for prices with scale of 2.
    """

    def test_init(self) -> None:
        """
        Test creating a new price.
        """

        self.assertEqual(str(Price('1')), '1.00')
        self.assertEqual(str(Price(1.0)), '1.00')
        self.assertEqual(str(Price(1.0001)), '1.00')
        self.assertEqual(str(Price(1)), '1.00')
        self.assertEqual(str(Price(Decimal('1.0'))), '1.00')

class BaseTest(unittest.TestCase):
    """
    Test for base ORM model.
    """

    def test_metadata(self) -> None:
        """
        Test SQL mapping metadata of models.
        """

        table = cast(Table, TestEntity.__table__)
        constraint = next(iter(table.foreign_key_constraints))
        self.assertEqual(constraint.name, 'fk_test_other_test')

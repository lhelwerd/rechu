"""
Tests for base model for receipt cataloging.
"""

from typing import cast, final
import unittest
from sqlalchemy import ForeignKey, Table
from sqlalchemy.orm import Mapped, mapped_column
from rechu.models.base import Base


@final
class TestEntity(Base):  # pylint: disable=too-few-public-methods
    """
    Test entity.
    """

    __tablename__ = "test"

    id: Mapped[int] = mapped_column(primary_key=True)
    other: Mapped[int] = mapped_column(ForeignKey("test.id"))


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
        self.assertEqual(constraint.name, "fk_test_other_test")

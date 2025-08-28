"""
Models for shop metadata.
"""

from typing import Optional
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import MappedColumn, Relationship, mapped_column, \
    relationship
from .base import Base

class Shop(Base): # pylint: disable=too-few-public-methods
    """
    Shop metadata model.
    """

    __tablename__ = "shop"

    key: MappedColumn[str] = mapped_column(String(32), primary_key=True)
    name: MappedColumn[Optional[str]] = mapped_column(String(32))
    website: MappedColumn[Optional[str]]
    wikidata: MappedColumn[Optional[str]]
    products: MappedColumn[Optional[str]]
    discount_indicators: Relationship[list["DiscountIndicator"]] = \
        relationship(back_populates="shop", cascade="all, delete-orphan",
                     passive_deletes=True, lazy="selectin")

    def copy(self) -> "Shop":
        """
        Copy the shop.
        """

        copy = Shop(key=self.key)
        copy.merge(self)
        return copy

    def merge(self, other: "Shop", override: bool = True) -> bool:
        """
        Merge attributes of the other shop into this one.

        This replaces values in this shop, except for the key which must be
        the same in order for .

        This is similar to a session merge except no database changes are done.

        If `override` is disabled, then simple property fields that already have
        a value are not changed.

        Returns whether the shop has changed with different values.
        """

        if self.key != other.key:
            raise ValueError("Both shops must have the same key: "
                             f"{self.key!r} != {other.key!r}")

        changed = False
        for field, meta in self.__table__.c.items():
            if (current := getattr(self, field) is not None and not override):
                continue

            target = getattr(other, field)
            if meta.nullable and target is not None and current != target:
                setattr(self, field, target)
                changed = True

        patterns = [indicator.pattern for indicator in self.discount_indicators]
        other_patterns = [
            indicator.pattern for indicator in other.discount_indicators
        ]
        if sorted(patterns) != sorted(other_patterns):
            self.discount_indicators = [
                DiscountIndicator(pattern=pattern) for pattern in other_patterns
            ]
            changed = True

        return changed

    def __repr__(self) -> str:
        return (f"Shop(key={self.key!r}, name={self.name!r}, "
                f"website={self.website!r}, wikidata={self.wikidata!r}, "
                f"products={self.products!r}, "
                f"discount_indicators={self.discount_indicators!r})")

class DiscountIndicator(Base): # pylint: disable=too-few-public-methods
    """
    Indicator model for a substring or regular expression that matches
    a receipt item's discount indicator.
    """

    __tablename__ = "shop_discount_indicator"

    id: MappedColumn[int] = mapped_column(primary_key=True)
    shop_id: MappedColumn[int] = mapped_column(ForeignKey("shop.key",
                                                          ondelete="CASCADE"))
    shop: Relationship[Shop] = \
        relationship(back_populates="discount_indicators")
    pattern: MappedColumn[str]

    def __repr__(self) -> str:
        return repr(self.pattern)

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

    def __repr__(self) -> str:
        return (f"Shop(key={self.key!r}, name={self.name!r}, "
                f"website={self.website!r}, wikidata={self.wikidata!r}, "
                f"products={self.products!r}, "
                f"discount_indicators={self.discount_indicators!r}")

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

"""
Models for product metadata.
"""

from typing import Optional
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base

class Product(Base): # pylint: disable=too-few-public-methods
    """
    Product model for metadata.
    """

    __tablename__ = "product"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    shop: Mapped[str] = mapped_column(String(32)) # shop.key

    # Descriptors
    brand: Mapped[Optional[str]]
    description: Mapped[Optional[str]]

    # Taxonomy
    category: Mapped[Optional[str]]
    type: Mapped[Optional[str]]

    # Trade item properties
    portions: Mapped[Optional[int]]
    weight: Mapped[Optional[str]]
    volume: Mapped[Optional[str]]
    alcohol: Mapped[Optional[str]]

    # Shop-specific and globally unique identifiers
    sku: Mapped[Optional[str]]
    gtin: Mapped[Optional[int]]

    def __repr__(self) -> str:
        return (f"Product(id={self.id!r}, shop={self.shop!r}, "
                f"brand={self.brand!r}, description={self.description!r}, "
                f"category={self.category!r}, type={self.type!r}, "
                f"portions={self.portions!r}, weight={self.weight!r}, "
                f"volume={self.volume!r}, alcohol={self.alcohol!r}, "
                f"sku={self.sku!r}, gtin={self.gtin!r})")

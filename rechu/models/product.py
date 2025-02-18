"""
Models for product metadata.
"""

from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base

class Product(Base): # pylint: disable=too-few-public-methods
    """
    Product model for metadata.
    """

    __tablename__ = "product"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

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

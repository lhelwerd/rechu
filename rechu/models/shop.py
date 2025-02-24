"""
Models for shop metadata.
"""

from typing import Optional
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base

class Shop(Base): # pylint: disable=too-few-public-methods
    """
    Shop metadata model.
    """

    __tablename__ = "shop"

    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(String(32))
    website: Mapped[Optional[str]]
    wikidata: Mapped[Optional[str]]

    def __repr__(self) -> str:
        return (f"Shop(key={self.key!r}, name={self.name!r}, "
                f"website={self.website!r}, wikidata={self.wikidata!r})")

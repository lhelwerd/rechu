"""
Models for shop metadata.
"""

from typing import Optional
from sqlalchemy import String
from sqlalchemy.orm import MappedColumn, mapped_column
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

    def __repr__(self) -> str:
        return (f"Shop(key={self.key!r}, name={self.name!r}, "
                f"website={self.website!r}, wikidata={self.wikidata!r})")

"""
Base model for receipt cataloging.
"""

from decimal import Decimal
from typing import Union
from sqlalchemy import BigInteger, MetaData, Numeric
from sqlalchemy.orm import DeclarativeBase, registry

_PriceNew = Union[Decimal, float, str]

class Price(Decimal):
    """
    Price type with scale of 2 (number of decimal places).
    """

    _quantize = Decimal('1.00')

    def __new__(cls, value: _PriceNew) -> "Price":
        return super().__new__(cls, Decimal(value).quantize(cls._quantize))

class GTIN(int):
    """
    Global trade item number identifier for products.
    """

class Base(DeclarativeBase): # pylint: disable=too-few-public-methods
    """
    Base ORM model class for receipt models.
    """

    metadata = MetaData(naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    })

    registry = registry(type_annotation_map={
        Price: Numeric(None, 2),
        GTIN: BigInteger
    })

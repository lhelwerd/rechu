"""
Attribute types for numeric values with discrete precision.
"""

from decimal import Decimal
from typing import Union
from sqlalchemy import BigInteger, Numeric
from .decorator import SerializableType

PriceNew = Union[Decimal, float, str]

class GTIN(int):
    """
    Global trade item number identifier for products.
    """

    def __repr__(self) -> str:
        parts = list(f"{self:_}")
        # Remove grouping around every other third digit
        del parts[-4::-8]
        return "".join(parts)

class Price(Decimal): # pylint: disable=too-few-public-methods
    """
    Price type with scale of 2 (number of decimal places).
    """

    _quantize = Decimal('1.00')

    def __new__(cls, value: PriceNew) -> "Price":
        try:
            return super().__new__(cls, Decimal(value).quantize(cls._quantize))
        except ArithmeticError as e:
            raise ValueError("Could not construct a two-decimal price") from e

class GTINType(SerializableType[GTIN, int]):
    # pylint: disable=too-many-ancestors
    """
    Type decoration handler for GTINs.
    """

    cache_ok = True
    impl = BigInteger()

    @property
    def serializable_type(self) -> type[GTIN]:
        return GTIN

    @property
    def serialized_type(self) -> type[int]:
        return int

class PriceType(SerializableType[Price, Decimal]):
    # pylint: disable=too-many-ancestors
    """
    Type decoration handler for prices.
    """

    cache_ok = True
    impl = Numeric(None, 2)

    @property
    def serializable_type(self) -> type[Price]:
        return Price

    @property
    def serialized_type(self) -> type[Decimal]:
        return Decimal

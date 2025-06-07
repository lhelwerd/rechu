"""
Type decorators for measurable types.
"""

from sqlalchemy import String
from .quantity import Quantity
from .unit import Unit
from ..decorator import SerializableType

class QuantityType(SerializableType[Quantity, str]):
    # pylint: disable=too-many-ancestors
    """
    Type decoration handler for quantities.
    """

    cache_ok = True
    impl = String()

    @property
    def serializable_type(self) -> type[Quantity]:
        return Quantity

    @property
    def serialized_type(self) -> type[str]:
        return str

class UnitType(SerializableType[Unit, str]):
    # pylint: disable=too-many-ancestors
    """
    Type decoration handler for units.
    """

    cache_ok = True
    impl = String()

    @property
    def serializable_type(self) -> type[Unit]:
        return Unit

    @property
    def serialized_type(self) -> type[str]:
        return str

"""
Type decorators for measurable types.
"""

from typing import final

from sqlalchemy import String
from typing_extensions import override

from ..decorator import SerializableType
from .quantity import Quantity
from .unit import Unit


@final
class QuantityType(SerializableType[Quantity, str]):
    # pylint: disable=too-many-ancestors
    """
    Type decoration handler for quantities.
    """

    cache_ok = True
    impl = String()

    @property
    @override
    def serializable_type(self) -> type[Quantity]:
        return Quantity

    @property
    @override
    def serialized_type(self) -> type[str]:
        return str


@final
class UnitType(SerializableType[Unit, str]):
    # pylint: disable=too-many-ancestors
    """
    Type decoration handler for units.
    """

    cache_ok = True
    impl = String()

    @property
    @override
    def serializable_type(self) -> type[Unit]:
        return Unit

    @property
    @override
    def serialized_type(self) -> type[str]:
        return str

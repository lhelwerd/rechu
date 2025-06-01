"""
Quantity type.
"""

from decimal import Decimal
from typing import Optional, Union
from pint.errors import UndefinedUnitError
from pint.facets.plain import PlainQuantity
from typing_extensions import Self
from .base import Measurable, UnitRegistry
from .unit import Unit, UnitNew

QuantityNew = Union["Quantity", PlainQuantity, Decimal, float, str]

@Measurable.register_wrapper(UnitRegistry.Quantity)
class Quantity(Measurable[PlainQuantity]):
    """
    A quantity value with an optional dimension with original input preserved.
    """

    def __init__(self, value: QuantityNew, unit: UnitNew = None) -> None:
        if isinstance(value, Quantity):
            value = str(value)
        elif isinstance(value, PlainQuantity) and value.dimensionless:
            value = value.magnitude
        if isinstance(unit, Unit):
            unit = str(unit)
        try:
            super().__init__(UnitRegistry.Quantity(value, units=unit))
        except UndefinedUnitError as error:
            raise ValueError("Could not create a quantity with unit") from error
        if unit is None or self.value.dimensionless:
            self._original = str(value)
        else:
            self._original = f"{value}{unit}"

    @property
    def amount(self) -> float:
        """
        Retrieve the magnitude of the quantity as a plain number.
        """

        return self.value.magnitude

    @property
    def unit(self) -> Optional[Unit]:
        """
        Retrieve the normalized unit of the quantity, or `None` if it has no
        unit dimensionality.
        """

        if self.value.dimensionless:
            return None

        return Unit(self.value.units)

    def __repr__(self) -> str:
        if self.value.dimensionless:
            return f"Quantity({self._original!r})"

        return f"Quantity('{self.amount!s}', '{self.value.units!s}')"

    def __str__(self) -> str:
        return self._original

    def __int__(self) -> int:
        return int(self.amount)

    def __float__(self) -> float:
        return float(self.amount)

    def __add__(self: Self, other: object) -> Self:
        return self.__class__(self.value + self._unwrap(other))

    def __sub__(self: Self, other: object) -> Self:
        return self.__class__(self.value - self._unwrap(other))

    def __floordiv__(self: Self, other: object) -> Self:
        return self.__class__(self.value // self._unwrap(other))

    def __mod__(self: Self, other: object) -> Self:
        return self.__class__(self.value % self._unwrap(other))

    def __pow__(self: Self, other: object) -> Self:
        return self.__class__(self.value ** self._unwrap(other))

    __radd__ = __add__

    def __rsub__(self: Self, other: object) -> Self:
        return self.__class__(self._unwrap(other) - self.value)

    def __rfloordiv__(self: Self, other: object) -> Self:
        return self.__class__(self._unwrap(other) // self.value)

    def __rmod__(self: Self, other: object) -> Self:
        return self.__class__(self._unwrap(other) % self.value)

    def __rpow__(self: Self, other: object) -> Self:
        return self.__class__(self._unwrap(other) ** self.value)

    def __neg__(self: Self) -> Self:
        return self.__class__(-self.value)

    def __pos__(self: Self) -> Self:
        return self.__class__(+self.value)

    def __abs__(self) -> Self:
        return self.__class__(abs(self.value))

    def __round__(self: Self, ndigits: Optional[int] = 0) -> Self:
        return self.__class__(round(self.value, ndigits=ndigits))

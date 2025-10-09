"""
Quantity type.
"""

from decimal import Decimal
from typing import Optional, Union, cast, TYPE_CHECKING
from pint.errors import UndefinedUnitError
from pint.facets.plain import PlainQuantity
from typing_extensions import Self, override
from .base import Measurable, UnitRegistry
from .unit import Unit, UnitNew
if TYPE_CHECKING:
    from .base import Dimension

QuantityNew = Optional[Union[
    "Measurable[Dimension, QuantityNew]", PlainQuantity[Decimal],
    Decimal, float, str
]]

@Measurable.register_wrapper(UnitRegistry.Quantity)
class Quantity(Measurable[PlainQuantity[Decimal], QuantityNew]):
    """
    A quantity value with an optional dimension with original input preserved.
    """

    def __init__(self, value: QuantityNew = None, /,
                 unit: UnitNew = None) -> None:
        if isinstance(value, Quantity):
            value = str(value)
        elif isinstance(value, PlainQuantity) and value.dimensionless:
            value = value.magnitude
        elif value is None:
            value = 0

        if isinstance(unit, Measurable):
            unit = str(unit)
        try:
            super().__init__(UnitRegistry.Quantity(value, units=unit))
        except UndefinedUnitError as error:
            raise ValueError("Could not create a quantity with unit") from error
        if unit is None or self.value.dimensionless:
            self._original: str = str(value)
        else:
            self._original = f"{value}{unit}"

    @property
    def amount(self) -> float:
        """
        Retrieve the magnitude of the quantity as a plain number.
        """

        return float(self.value.magnitude)

    @property
    def unit(self) -> Optional[Unit]:
        """
        Retrieve the normalized unit of the quantity, or `None` if it has no
        unit dimensionality.
        """

        if self.value.dimensionless:
            return None

        return Unit(self.value.units)

    @override
    def __repr__(self) -> str:
        if self.value.dimensionless:
            return f"Quantity({self._original!r})"

        return f"Quantity('{self.amount!s}', '{self.value.units!s}')"

    @override
    def __str__(self) -> str:
        return self._original

    def __int__(self) -> int:
        return int(self.amount)

    def __float__(self) -> float:
        return float(self.amount)

    def __add__(self: Self, other: object) -> Self:
        return self.__class__(cast(PlainQuantity[Decimal],
                                   self.value + self._unwrap(other)))

    def __sub__(self: Self, other: object) -> Self:
        return self.__class__(self.value - self._unwrap(other))

    def __floordiv__(self: Self, other: object) -> Self:
        return self.__class__(self.value // self._unwrap(other))

    def __mod__(self: Self, other: object) -> Self:
        return self.__class__(self.value % self._unwrap(other))

    def __pow__(self: Self, other: object) -> Self:
        return self.__class__(self.value ** self._unwrap(other))

    def __radd__(self: Self, other: object) -> Self:
        return self.__class__(cast(PlainQuantity[Decimal],
                                   self._unwrap(other) + self.value))

    def __rsub__(self: Self, other: object) -> Self:
        return self.__class__(cast(PlainQuantity[Decimal],
                                   self._unwrap(other) - self.value))

    def __rfloordiv__(self: Self, other: object) -> Self:
        return self.__class__(self._unwrap(other) // self.value)

    def __rmod__(self: Self, other: object) -> Self:
        return self.__class__(self._unwrap(other) % self.value)

    def __rpow__(self: Self, other: object) -> Self:
        return self.__class__(cast(PlainQuantity[Decimal],
                                   self._unwrap(other) ** self.value))

    def __neg__(self: Self) -> Self:
        return self.__class__(-self.value)

    def __pos__(self: Self) -> Self:
        return self.__class__(+self.value)

    def __abs__(self) -> Self:
        return self.__class__(abs(self.value))

    def __round__(self: Self, ndigits: Optional[int] = 0) -> Self:
        return self.__class__(round(self.value, ndigits=ndigits))

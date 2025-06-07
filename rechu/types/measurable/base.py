"""
Base type for measurable quantities and units.
"""

from decimal import Decimal
from typing import Callable, Generic, TypeVar, Union
import pint
from pint.facets.plain import PlainQuantity, PlainUnit
from typing_extensions import Self, TypeGuard

Dimension = Union[PlainQuantity, PlainUnit]
DimensionT = TypeVar("DimensionT", bound=Dimension)
MeasurableT = TypeVar("MeasurableT", bound="Measurable")

UnitRegistry = pint.UnitRegistry(cache_folder=":auto:", non_int_type=Decimal)

class Measurable(Generic[DimensionT]):
    """
    A value that has operations to convert or derive it.
    """

    _wrappers: dict[type[Dimension], type["Measurable"]] = {}

    @classmethod
    def register_wrapper(cls, dimension: type[Dimension]) \
            -> Callable[[type["Measurable"]], type["Measurable"]]:
        """
        Register a measurable type which can wrap a `pint` dimension type.
        """

        def decorator(subclass: type["Measurable"]) -> type["Measurable"]:
            cls._wrappers[dimension] = subclass
            return subclass

        return decorator

    def __init__(self, value: DimensionT) -> None:
        super().__init__()
        self.value = value

    def _can_wrap(self, dimension: type[object]) -> TypeGuard[type[Dimension]]:
        return dimension in self._wrappers

    def _wrap(self, new: object) -> "Measurable":
        dimension = type(new)
        if self._can_wrap(dimension):
            return self._wrappers[dimension](new)

        raise TypeError("Could not convert to measurable object")

    @staticmethod
    def _unwrap(other: object) -> object:
        if isinstance(other, Measurable):
            return other.value
        return other

    def __lt__(self, other: object) -> bool:
        return self.value < self._unwrap(other)

    def __le__(self, other: object) -> bool:
        return self.value <= self._unwrap(other)

    def __eq__(self, other: object) -> bool:
        return self.value == self._unwrap(other)

    def __ne__(self, other: object) -> bool:
        return self.value != self._unwrap(other)

    def __gt__(self, other: object) -> bool:
        return self.value > self._unwrap(other)

    def __ge__(self, other: object) -> bool:
        return self.value >= self._unwrap(other)

    def __hash__(self) -> int:
        return hash(self.value)

    def __bool__(self) -> bool:
        return bool(self.value)

    def __mul__(self, other: object) -> "Measurable":
        return self._wrap(self.value * self._unwrap(other))

    def __truediv__(self: Self, other: object) -> "Measurable":
        return self._wrap(self.value / self._unwrap(other))

    __rmul__ = __mul__

    def __rtruediv__(self, other: object) -> "Measurable":
        return self._wrap(self._unwrap(other) / self.value)

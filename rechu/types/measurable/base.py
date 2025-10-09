"""
Base type for measurable quantities and units.
"""

from decimal import Decimal
from typing import Any, Callable, ClassVar, Generic, Optional, TypeVar, Union, \
    cast
from pint import UnitRegistry as PlainRegistry
from pint.facets.plain import PlainQuantity, PlainUnit
from typing_extensions import Self, TypeGuard, override

Dimension = Union[PlainQuantity[Decimal], PlainUnit]
DimensionT_co = TypeVar("DimensionT_co", bound=Dimension, covariant=True)
MeasurableT = TypeVar("MeasurableT", bound="Measurable[Dimension, Any]")
NewT = TypeVar("NewT")

UnitRegistry = \
    PlainRegistry(cache_folder=":auto:",
                  non_int_type=Decimal) # pyright: ignore[reportArgumentType]

class Measurable(Generic[DimensionT_co, NewT]):
    """
    A value that has operations to convert or derive it.
    """

    _wrappers: ClassVar[dict[type[Dimension],
                             type["Measurable[Dimension, Any]"]]] = {}

    @classmethod
    def register_wrapper(cls, dimension: type[Dimension]) \
            -> Callable[[type[MeasurableT]], type[MeasurableT]]:
        """
        Register a measurable type which can wrap a `pint` dimension type.
        """

        def decorator(subclass: type[MeasurableT]) -> type[MeasurableT]:
            cls._wrappers[dimension] = subclass
            return subclass

        return decorator

    def __new__(cls, value: Optional[NewT] = None, /,
                *a: Any, **kw: Any) -> Self: # pyright: ignore[reportAny]
        """
        Create the measurable object based on accepted input types.
        """

        return super().__new__(cls)

    def __init__(self, value: Optional[NewT] = None, /,
                 *a: Any, **kw: Any) -> None: # pyright: ignore[reportAny]
        # pylint: disable=unused-argument
        super().__init__()
        self.value: DimensionT_co = cast(DimensionT_co, value)

    def _can_wrap(self, dimension: type[object]) -> TypeGuard[type[Dimension]]:
        return dimension in self._wrappers

    def _wrap(self, new: NewT) -> "Measurable[Dimension, NewT]":
        dimension = type(new)
        if self._can_wrap(dimension):
            return self._wrappers[dimension](new)

        raise TypeError("Could not convert to measurable object")

    @staticmethod
    def _unwrap(other: object) -> Dimension:
        if isinstance(other, Measurable):
            return other.value
        return cast(Dimension, other)

    def __lt__(self, other: object) -> bool:
        return cast(bool, self.value < self._unwrap(other))

    def __le__(self, other: object) -> bool:
        return cast(bool, self.value <= self._unwrap(other))

    @override
    def __eq__(self, other: object) -> bool:
        return cast(bool, self.value == self._unwrap(other))

    @override
    def __ne__(self, other: object) -> bool:
        return cast(bool, self.value != self._unwrap(other))

    def __gt__(self, other: object) -> bool:
        return cast(bool, self.value > self._unwrap(other))

    def __ge__(self, other: object) -> bool:
        return cast(bool, self.value >= self._unwrap(other))

    @override
    def __hash__(self) -> int:
        return hash(self.value)

    def __bool__(self) -> bool:
        return bool(self.value)

    def __mul__(self, other: object) -> "Measurable[Dimension, NewT]":
        return self._wrap(cast(NewT, self.value * self._unwrap(other)))

    def __truediv__(self: Self, other: object) -> "Measurable[Dimension, NewT]":
        return self._wrap(cast(NewT, self.value / self._unwrap(other)))

    def __rmul__(self, other: object) -> "Measurable[Dimension, NewT]":
        return self._wrap(cast(NewT, self._unwrap(other) * self.value))

    def __rtruediv__(self, other: object) -> "Measurable[Dimension, NewT]":
        return self._wrap(cast(NewT, self._unwrap(other) / self.value))

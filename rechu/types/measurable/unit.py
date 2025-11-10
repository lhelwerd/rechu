"""
Unit type.
"""

from typing import TypeAlias

from pint.facets.plain import PlainUnit
from typing_extensions import override

from .base import Measurable, UnitRegistry

_UnitNew = PlainUnit | str | None
UnitNew: TypeAlias = "Measurable[PlainUnit, UnitNew] | _UnitNew"


@Measurable.register_wrapper(UnitRegistry.Unit)
class Unit(Measurable[PlainUnit, UnitNew]):
    """
    A normalized unit value.
    """

    def __init__(self, unit: UnitNew = None, /) -> None:
        if isinstance(unit, Measurable):
            unit = str(unit)
        elif unit is None:
            unit = ""
        super().__init__(UnitRegistry.Unit(unit))

    @override
    def __repr__(self) -> str:
        return f"Unit('{self.value!s}')"

    @override
    def __str__(self) -> str:
        return str(self.value)

    @override
    def __bool__(self) -> bool:
        return not self.value.dimensionless

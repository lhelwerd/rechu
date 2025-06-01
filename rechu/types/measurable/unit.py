"""
Unit type.
"""

from typing import Optional, Union
from pint.facets.plain import PlainUnit
from .base import Measurable, UnitRegistry

UnitNew = Optional[Union["Unit", PlainUnit, str]]

@Measurable.register_wrapper(UnitRegistry.Unit)
class Unit(Measurable[PlainUnit]):
    """
    A normalized unit value.
    """

    def __init__(self, unit: UnitNew) -> None:
        if isinstance(unit, Unit):
            unit = str(unit)
        elif unit is None:
            unit = ""
        super().__init__(UnitRegistry.Unit(unit))

    def __repr__(self) -> str:
        return f"Unit('{self.value!s}')"

    def __str__(self) -> str:
        return str(self.value)

    def __bool__(self) -> bool:
        return not self.value.dimensionless

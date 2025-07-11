"""
Tests for type decorators of measurable types.
"""

from rechu.types.measurable.decorator import QuantityType, UnitType
from rechu.types.measurable.quantity import Quantity
from rechu.types.measurable.unit import Unit
from ..decorator import SerializableTypeTestCase

class QuantityTypeTest(SerializableTypeTestCase[Quantity, str]):
    """
    Tests for type decoration handler of quantities.
    """

    type_decorator = QuantityType
    value = Quantity("0.5kg")
    representation = "0.5kg"

class UnitTypeTest(SerializableTypeTestCase[Unit, str]):
    """
    Tests for type decoration handler of units.
    """

    type_decorator = UnitType
    value = Unit("kg")
    representation = "kilogram"

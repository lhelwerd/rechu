"""
Tests for unit type.
"""

from rechu.types.measurable import Quantity, Unit
from .base import MeasurableTestCase

class UnitTest(MeasurableTestCase[Unit]):
    """
    Tests for normalized unit value.
    """

    value = Unit("g")
    same = Unit("g")
    bigger = Unit("kg")
    smaller = Unit("mg")
    empty = Unit(None)

    def test_mul(self) -> None:
        """
        Test the multiplication operator.
        """

        self.assertEqual(self.value * self.same, Unit("g ** 2"))
        self.assertNotEqual(self.value * self.bigger, Unit("g ** 2"))
        self.assertEqual(1 * self.value, Quantity(1, "g"))

    def test_truediv(self) -> None:
        """
        Test the true division operator.
        """

        self.assertEqual(self.value / self.same, self.empty)
        self.assertEqual(1 / self.value, Quantity(1, "1 / g"))

    def test_repr(self) -> None:
        """
        Test the string representation of the value.
        """

        self.assertEqual(repr(self.value), "Unit('gram')")
        self.assertEqual(repr(self.empty), "Unit('dimensionless')")
        self.assertEqual(repr(self.bigger), "Unit('kilogram')")
        self.assertEqual(repr(Unit(self.empty)), "Unit('dimensionless')")

    def test_str(self) -> None:
        """
        Test the string conversion of the value.
        """

        self.assertEqual(str(self.value), "gram")
        self.assertEqual(str(self.empty), "dimensionless")
        self.assertEqual(str(self.bigger), "kilogram")
        self.assertEqual(str(Unit(self.empty)), "dimensionless")

"""
Tests for quantity type.
"""

from decimal import Decimal
from rechu.types.measurable import Quantity, Unit
from .base import MeasurableTestCase

class QuantityTest(MeasurableTestCase[Quantity]):
    """
    Tests for quantity value with optional dimension and original input.
    """

    value = Quantity("1")
    same = Quantity("1")
    bigger = Quantity("2")
    smaller = Quantity("0.50")
    empty = Quantity(0)
    dimensional = Quantity("1kg")

    def test_amount(self) -> None:
        """
        Test retrieving the magnitude.
        """

        self.assertEqual(self.value.amount, 1.0)
        self.assertEqual(self.smaller.amount, 0.5)
        self.assertEqual(self.dimensional.amount, 1.0)

    def test_unit(self) -> None:
        """
        Test retrieving the normalized unit of the quantity.
        """

        self.assertIsNone(self.value.unit)
        self.assertEqual(self.dimensional.unit, Unit("kg"))

    def test_repr(self) -> None:
        """
        Test the string representation of the value.
        """

        self.assertEqual(repr(self.value), "Quantity('1')")
        self.assertEqual(repr(self.smaller), "Quantity('0.50')")
        self.assertEqual(repr(self.empty), "Quantity('0')")
        self.assertEqual(repr(self.dimensional), "Quantity('1', 'kilogram')")
        self.assertEqual(repr(Quantity('1', unit=Unit(None))), "Quantity('1')")
        self.assertEqual(repr(Quantity(self.smaller)), "Quantity('0.50')")

    def test_str(self) -> None:
        """
        Test the string conversion of the value.
        """

        self.assertEqual(str(self.value), '1')
        self.assertEqual(str(self.smaller), '0.50')
        self.assertEqual(str(self.empty), '0')
        self.assertEqual(str(self.dimensional), '1kg')
        self.assertEqual(str(Quantity('1', unit=Unit(None))), '1')
        self.assertEqual(str(self.value + self.bigger), '3')
        # Arithmetic with units loses the original unit spelling for now.
        self.assertEqual(str(self.dimensional * 5), '5 kilogram')
        self.assertEqual(str(Quantity(self.dimensional)), '1kg')

    def test_int(self) -> None:
        """
        Test the integer conversion of the value.
        """

        self.assertEqual(int(self.value), 1)
        self.assertEqual(int(self.smaller), 0)
        self.assertEqual(int(self.empty), 0)
        self.assertEqual(int(self.dimensional), 1)

    def test_float(self) -> None:
        """
        Test the floating point conversion of the value.
        """

        self.assertEqual(float(self.value), 1.0)
        self.assertEqual(float(self.smaller), 0.5)
        self.assertEqual(float(self.empty), 0.0)
        self.assertEqual(float(self.dimensional), 1.0)

    def test_add(self) -> None:
        """
        Test the addition operator.
        """

        self.assertEqual(self.value + self.same, Quantity('2'))
        self.assertEqual(self.value + self.empty, self.value)
        self.assertEqual(self.value + Decimal('0.75'), Quantity('1.75'))

    def test_sub(self) -> None:
        """
        Test the subtraction operator.
        """

        self.assertEqual(self.value - self.same, self.empty)
        self.assertEqual(self.value - self.empty, self.value)
        self.assertEqual(self.value - self.smaller, self.smaller)
        self.assertEqual(Decimal('1.25') - self.value, Quantity('0.25'))

    def test_mul(self) -> None:
        """
        Test the multiplication operator.
        """

        self.assertEqual(self.value * self.same, self.value)
        self.assertEqual(self.value * self.bigger, self.bigger)
        self.assertEqual(self.smaller * self.bigger, self.value)
        self.assertEqual(Decimal('0.5') * self.value, self.smaller)
        self.assertEqual(self.dimensional * Quantity("2kg"), Quantity("2kg**2"))

    def test_truediv(self) -> None:
        """
        Test the true division operator.
        """

        self.assertEqual(self.value / self.same, self.value)
        self.assertEqual(self.value / self.bigger, self.smaller)
        self.assertEqual(self.dimensional / self.bigger, Quantity("0.5kg"))
        self.assertEqual(self.dimensional / Quantity("4kg"), Quantity("0.25"))
        self.assertEqual(1 / self.smaller, Quantity('2'))

    def test_floordiv(self) -> None:
        """
        Test the floor division operator.
        """

        self.assertEqual(self.value // self.same, self.value)
        self.assertEqual(self.value // self.bigger, self.empty)
        self.assertEqual(self.dimensional // Quantity("0.5kg"), self.bigger)
        self.assertEqual(7 // self.bigger, Quantity("3"))

    def test_mod(self) -> None:
        """
        Test the modulo operator.
        """

        self.assertEqual(self.value % self.bigger, self.value)
        self.assertEqual(self.bigger % self.value, self.empty)
        self.assertEqual(self.dimensional % Quantity("2kg"), self.dimensional)
        self.assertEqual(10 % self.bigger, self.empty)

    def test_pow(self) -> None:
        """
        Test the power operator.
        """

        self.assertEqual(self.value ** self.bigger, self.value)
        self.assertEqual(self.smaller ** self.bigger, Quantity('0.25'))
        self.assertEqual(5 ** self.bigger, Quantity('25'))
        self.assertEqual(self.dimensional ** self.bigger, Quantity("1kg**2"))

    def test_neg(self) -> None:
        """
        Test the negation operator.
        """

        self.assertEqual(-self.value, Quantity("-1"))
        self.assertEqual(-self.empty, self.empty)
        self.assertEqual(-self.dimensional, Quantity("-1kg"))

    def test_pos(self) -> None:
        """
        Test the positive operator.
        """

        self.assertEqual(+self.value, self.value)
        self.assertEqual(+self.dimensional, self.dimensional)

    def test_abs(self) -> None:
        """
        Test the absolute operator.
        """

        self.assertEqual(abs(self.value), self.value)
        self.assertEqual(abs(Quantity("-0.5")), self.smaller)
        self.assertEqual(abs(self.dimensional), self.dimensional)

    def test_round(self) -> None:
        """
        Test the rounding operator.
        """

        tests = [
            (round(self.value), self.value),
            (round(self.smaller), self.empty),
            (round(self.smaller, 1), self.smaller),
            (round(self.dimensional), self.dimensional)
        ]
        for rounded, target in tests:
            with self.subTest(rounded=rounded):
                self.assertEqual(rounded, target)

"""
Tests for attribute types of numeric values with discrete precision.
"""

from decimal import Decimal
import unittest
from rechu.types.quantized import GTIN, Price, GTINType, PriceType
from .decorator import SerializableTypeTestCase

class GTINTest(unittest.TestCase):
    """
    Tests for global trade item number identifier.
    """

    def test_repr(self) -> None:
        """
        Test the string representation of the number.
        """

        self.assertEqual(repr(GTIN(1234567890)), '1234_567890')
        self.assertEqual(repr(GTIN(9781234567890)), '9_781234_567890')
        self.assertEqual(repr(GTIN(0)), '0')
        self.assertEqual(repr(GTIN(4241929)), '4_241929')

class PriceTest(unittest.TestCase):
    """
    Tests for prices with scale of 2.
    """

    def test_init(self) -> None:
        """
        Test creating a new price.
        """

        self.assertEqual(str(Price('1')), '1.00')
        self.assertEqual(str(Price(1.0)), '1.00')
        self.assertEqual(str(Price(1.0001)), '1.00')
        self.assertEqual(str(Price(1)), '1.00')
        self.assertEqual(str(Price(Decimal('1.0'))), '1.00')
        with self.assertRaisesRegex(ValueError, 'Could not construct .* price'):
            self.assertNotEqual(str(Price('?')), '?')

class GTINTypeTest(SerializableTypeTestCase[GTIN, int]):
    """
    Tests for type decoration handler of GTINs.
    """

    type_decorator = GTINType
    value = GTIN(1234567890123)
    representation = 1234567890123

class PriceTypeTest(SerializableTypeTestCase[Price, Decimal]):
    """
    Tests for type decoration handler of prices.
    """

    type_decorator = PriceType
    value = Price("1.00")
    representation = Decimal("1.00")

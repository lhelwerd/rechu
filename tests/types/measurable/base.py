"""
Tests for base type of measurable quantities and units.
"""

from decimal import Decimal
import operator
from typing import Generic, cast
import unittest
from pint.facets.plain import PlainQuantity
from rechu.types.measurable.base import Measurable, MeasurableT

class FakeQuantity(PlainQuantity):
    """
    Test quantity type.
    """

@Measurable.register_wrapper(FakeQuantity)
class Measurement(Measurable[FakeQuantity, object]):
    # pylint: disable=too-few-public-methods
    """
    Test measurable type which does not always properly wrap its dimensions.
    """

    def __add__(self, other: object) -> "Measurable":
        result = cast(PlainQuantity[Decimal], self._unwrap(other) + self.value)
        if self.value.dimensionless:
            return self._wrap(float(result))
        return self._wrap(result)

class MeasurableTestCase(unittest.TestCase, Generic[MeasurableT]):
    """
    Test case base class for measurable values.
    """

    value: MeasurableT
    same: MeasurableT
    bigger: MeasurableT
    smaller: MeasurableT
    empty: MeasurableT

    def setUp(self) -> None:
        super().setUp()
        if self.__class__ is MeasurableTestCase and \
            self._testMethodName != 'test_register_wrapper':
            raise unittest.SkipTest("Generic class is not tested")

    def test_register_wrapper(self) -> None:
        """
        Test registering a measurable type for wrapping and unwrapping purposes.
        """

        good = [FakeQuantity(4, 'kg'), FakeQuantity(2, 'kg')]
        bad = [FakeQuantity(1.3), FakeQuantity(5)]
        self.assertIsInstance(Measurement(good[0]) + Measurement(good[1]),
                              Measurement)
        with self.assertRaisesRegex(TypeError,
                                    "Could not convert to measurable object"):
            self.assertNotIsInstance(Measurement(bad[0]) + Measurement(bad[1]),
                                     Measurement)

    def test_eq(self) -> None:
        """
        Test the equality operator.
        """

        self.assertTrue(operator.eq(self.value, self.same))
        self.assertFalse(operator.eq(self.value, self.bigger))

    def test_ne(self) -> None:
        """
        Test the inquality operator.
        """

        self.assertTrue(operator.ne(self.value, self.bigger))
        self.assertFalse(operator.ne(self.value, self.same))

    def test_lt(self) -> None:
        """
        Test the less than operator.
        """

        self.assertTrue(operator.lt(self.value, self.bigger))
        self.assertFalse(operator.lt(self.value, self.same))
        self.assertFalse(operator.lt(self.value, self.smaller))

    def test_le(self) -> None:
        """
        Test the less than or equals operator.
        """

        self.assertTrue(operator.le(self.value, self.bigger))
        self.assertTrue(operator.le(self.value, self.same))
        self.assertFalse(operator.le(self.value, self.smaller))

    def test_gt(self) -> None:
        """
        Test the greater than operator.
        """

        self.assertTrue(operator.gt(self.value, self.smaller))
        self.assertFalse(operator.gt(self.value, self.same))
        self.assertFalse(operator.gt(self.value, self.bigger))

    def test_ge(self) -> None:
        """
        Test the greater than or equals operator.
        """

        self.assertTrue(operator.ge(self.value, self.smaller))
        self.assertTrue(operator.ge(self.value, self.same))
        self.assertFalse(operator.ge(self.value, self.bigger))

    def test_hash(self) -> None:
        """
        Test the hash function.
        """

        self.assertEqual(hash(self.value), hash(self.same))
        self.assertNotEqual(hash(self.value), hash(self.bigger))

    def test_bool(self) -> None:
        """
        Test the boolean operator.
        """

        self.assertTrue(bool(self.value))
        self.assertFalse(bool(self.empty))

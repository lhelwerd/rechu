"""
Tests for type decorators of model type annotation maps.
"""

import unittest
from typing import Generic

from typing_extensions import override

from rechu.types.decorator import ST, SerializableType, T
from rechu.types.measurable.base import Measurable

from ..database import DatabaseTestCase


class SerializableTypeTestCase(DatabaseTestCase, Generic[T, ST]):
    """
    Test case base class for type decoration handler of serializable values.
    """

    type_decorator: type[SerializableType[T, ST]] = SerializableType
    value: T
    representation: ST

    @override
    def setUp(self) -> None:
        super().setUp()
        if (
            self.__class__ is SerializableTypeTestCase
            and self._testMethodName != "test_type"
        ):
            raise unittest.SkipTest("Generic class is not tested")
        self._type: SerializableType[T, ST] = self.type_decorator()

    def test_process_literal_param(self) -> None:
        """
        Test retrieviing a literal parameter value.
        """

        dialect = self.database.engine.dialect
        self.assertEqual(
            self._type.process_literal_param(None, dialect), "NULL"
        )
        if isinstance(self.representation, str):
            representation = repr(self.representation)
        else:
            representation = str(self.representation)
        self.assertEqual(
            self._type.process_literal_param(self.value, dialect),
            representation,
        )

    def test_process_bind_param(self) -> None:
        """
        Test retrieving a bound parameter value.
        """

        dialect = self.database.engine.dialect
        self.assertIsNone(self._type.process_bind_param(None, dialect))
        self.assertEqual(
            self._type.process_bind_param(self.value, dialect),
            self.representation,
        )

    def test_process_result_value(self) -> None:
        """
        Test retrieving a result row column value.
        """

        dialect = self.database.engine.dialect
        self.assertIsNone(self._type.process_result_value(None, dialect))
        self.assertEqual(
            self._type.process_result_value(self.representation, dialect),
            self.value,
        )

    def test_type(self) -> None:
        """
        Test retrieving the Python type.
        """

        if self.__class__ is SerializableTypeTestCase:
            with self.assertRaises(NotImplementedError):
                self.assertNotEqual(self._type.serializable_type, Measurable)
            with self.assertRaises(NotImplementedError):
                self.assertNotEqual(self._type.serialized_type, str)
        else:
            self.assertEqual(self._type.python_type, type(self.value))
            self.assertEqual(self._type.serializable_type, type(self.value))
            self.assertEqual(
                self._type.serialized_type, type(self.representation)
            )

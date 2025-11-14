"""
Type decorators for model type annotation maps.
"""

from typing import Any, Generic, Protocol, TypeVar

from sqlalchemy.engine import Dialect
from sqlalchemy.types import String, TypeDecorator, TypeEngine
from typing_extensions import Self, override


class Convertible(Protocol):
    # pylint: disable=too-few-public-methods
    """
    A type which can be created from another input type.
    """

    def __new__(
        cls: type[Self],
        value: Any,  # pyright: ignore[reportAny]
        /,
    ) -> Self:
        """
        Create the object based on accepted input values.
        """

        raise NotImplementedError("Type must implement class creation")


T = TypeVar("T", bound=Convertible)
ST = TypeVar("ST", bound=Convertible)


class SerializableType(TypeDecorator[T], Generic[T, ST]):
    # pylint: disable=too-many-ancestors
    """
    Type decoration handler for attributes.
    """

    # Default implementation
    impl: TypeEngine[Any] | type[TypeEngine[Any]] = String()

    @override
    def process_literal_param(self, value: T | None, dialect: Dialect) -> str:
        if value is None:
            return "NULL"
        impl = self.impl if isinstance(self.impl, TypeEngine) else self.impl()
        processor = impl.literal_processor(dialect)
        if processor is None:  # pragma: no cover
            raise TypeError("There should be a literal processor for SQL type")
        return processor(self.serialized_type(value))

    @override
    def process_bind_param(
        self, value: T | None, dialect: Dialect
    ) -> ST | None:
        if value is None:
            return None
        return self.serialized_type(value)

    @override
    def process_result_value(
        self, value: Any | None, dialect: Dialect
    ) -> T | None:
        if value is None:
            return None
        return self.serializable_type(value)

    @property
    @override
    def python_type(self) -> type[Any]:
        return self.serializable_type

    @property
    def serializable_type(self) -> type[T]:
        """
        Retrieve the type to use for result values of this serialized type.
        """

        raise NotImplementedError("Must be implemented by subclasses")

    @property
    def serialized_type(self) -> type[ST]:
        """
        Retrieve the type to use for storing the values in the database.
        """

        raise NotImplementedError("Must be implemented by subclasses")

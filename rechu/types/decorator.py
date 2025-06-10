"""
Type decorators for model type annotation maps.
"""

from typing import Any, Generic, Optional, Protocol, TypeVar
from sqlalchemy.engine import Dialect
from sqlalchemy.types import String, TypeDecorator, TypeEngine
from typing_extensions import Self

class Convertible(Protocol):
    # pylint: disable=too-few-public-methods
    """
    A type which can be created from another input type.
    """

    def __new__(cls: type[Self], value: object) -> Self:
        ...

T = TypeVar('T', bound=Convertible)
ST = TypeVar('ST', bound=Convertible)

class SerializableType(TypeDecorator[T], Generic[T, ST]):
    # pylint: disable=too-many-ancestors
    """
    Type decoration handler for attributes.
    """

    # Default implementation
    impl: TypeEngine = String()

    def process_literal_param(self, value: Optional[T],
                              dialect: Dialect) -> str:
        if value is None:
            return "NULL"
        processor = self.impl.literal_processor(dialect)
        if processor is None: # pragma: no cover
            raise TypeError("There should be a literal processor for SQL type")
        return processor(self.serialized_type(value))

    def process_bind_param(self, value: Optional[T], dialect: Dialect) -> Any:
        if value is None:
            return None
        return self.serialized_type(value)

    def process_result_value(self, value: Optional[Any],
                             dialect: Dialect) -> Optional[T]:
        if value is None:
            return None
        return self.serializable_type(value)

    @property
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

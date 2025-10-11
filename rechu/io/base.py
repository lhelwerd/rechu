"""
Abstract base classes for file reading, writing and parsing.
"""

from abc import ABCMeta, abstractmethod
from collections.abc import Collection, Iterator
from datetime import datetime
from enum import Enum
import logging
import os
from pathlib import Path
import re
from typing import (
    Generic,
    Optional,
    TextIO,
    TypeVar,
    cast,
    get_origin,
    TYPE_CHECKING,
)
from typing_extensions import is_typeddict
import yaml
from yaml.parser import ParserError
from rechu.models.base import Base, GTIN, Price, Quantity

if TYPE_CHECKING:
    from _typeshed import OpenTextModeReading, OpenTextModeWriting
else:
    OpenTextModeReading = str
    OpenTextModeWriting = str

LOGGER = logging.getLogger(__name__)

# Model being read/written
T = TypeVar("T", bound=Base)
# Representation of model in serializable form
RT = TypeVar("RT")


class Reader(Generic[T], metaclass=ABCMeta):
    """
    File reader.
    """

    _mode: OpenTextModeReading = "r"
    _encoding: str = "utf-8"

    def __init__(self, path: Path, updated: datetime = datetime.min) -> None:
        self._path: Path = path
        self._updated: datetime = updated

    @property
    def path(self) -> Path:
        """
        Retrieve the path from which to read the models.
        """

        return self._path

    def read(self) -> Iterator[T]:
        """
        Read the file from the path and yield specific models from it.
        """

        with self._path.open(self._mode, encoding=self._encoding) as file:
            yield from self.parse(file)

    @abstractmethod
    def parse(self, file: TextIO) -> Iterator[T]:
        """
        Parse an open file and yield specific models from it.

        This method raises `TypeError` or subclasses if certain data in the
        file does not have the correct type, and `ValueError` or subclasses if
        the data has inconsistent or out-of-range values.
        """

        raise NotImplementedError("Must be implemented by subclasses")


class YAMLReader(Reader[T], metaclass=ABCMeta):
    """
    YAML file reader.
    """

    def load(self, file: TextIO, expected: type[RT]) -> RT:
        """
        Load the YAML file as a Python value.
        """

        try:
            if is_typeddict(expected):
                expected = cast(type, expected.__base__)
            elif (origin := get_origin(expected)) is not None:
                expected = cast(type, origin)
            else:  # pragma: no cover
                LOGGER.warning(
                    "Expected typing annotations for load, got %r", expected
                )

            data = yaml.safe_load(file)  # pyright: ignore[reportAny]
            if isinstance(data, expected):
                return data
            raise TypeError(f"File '{self.path}' does not contain {expected}")
        except ParserError as error:
            raise TypeError(
                f"YAML failure in file '{self._path}' {error}"
            ) from error


class Writer(Generic[T], metaclass=ABCMeta):
    """
    File writer.
    """

    _mode: OpenTextModeWriting = "w"
    _encoding: str = "utf-8"

    def __init__(
        self,
        path: Path,
        models: Collection[T],
        updated: Optional[datetime] = None,
    ) -> None:
        self._path: Path = path
        self._models: Collection[T] = models
        self._updated: Optional[datetime] = updated

    @property
    def path(self) -> Path:
        """
        Retrieve the path to which to write the models.
        """

        return self._path

    def write(self) -> None:
        """
        Write the models to the path.
        """

        with self._path.open(self._mode, encoding=self._encoding) as file:
            self.serialize(file)

        if self._updated is not None:
            os.utime(
                self._path,
                times=(self._updated.timestamp(), self._updated.timestamp()),
            )

    @abstractmethod
    def serialize(self, file: TextIO) -> None:
        """
        Write a serialized variant of the models to the open file.
        """

        raise NotImplementedError("Must be implemented by subclasses")


class YAMLTag(str, Enum):
    """
    Explicit type tags for YAML.
    """

    INT = "tag:yaml.org,2002:int"
    FLOAT = "tag:yaml.org,2002:float"
    STR = "tag:yaml.org,2002:str"


class YAMLWriter(Writer[T], Generic[T, RT], metaclass=ABCMeta):
    """
    YAML file writer.
    """

    @classmethod
    def _represent_gtin(cls, dumper: yaml.Dumper, data: GTIN) -> yaml.Node:
        return dumper.represent_scalar(YAMLTag.INT, f"{data:0>14}")

    @classmethod
    def _represent_price(cls, dumper: yaml.Dumper, data: Price) -> yaml.Node:
        return dumper.represent_scalar(YAMLTag.FLOAT, str(data))

    @classmethod
    def _represent_quantity(
        cls, dumper: yaml.Dumper, data: Quantity
    ) -> yaml.Node:
        if data.unit:
            return dumper.represent_scalar(YAMLTag.STR, str(data))
        return dumper.represent_scalar(YAMLTag.INT, str(int(data)))

    def save(self, data: RT, file: TextIO) -> None:
        """
        Save the YAML file from a Python value.
        """

        yaml.add_implicit_resolver(
            YAMLTag.INT, re.compile(r"^\d{14}$"), list("0123456789")
        )
        yaml.add_representer(GTIN, self._represent_gtin)
        yaml.add_representer(Price, self._represent_price)
        yaml.add_representer(Quantity, self._represent_quantity)
        yaml.dump(
            data,
            file,
            width=80,
            indent=2,
            default_flow_style=None,
            sort_keys=False,
        )

"""
Abstract base classes for file reading, writing and parsing.
"""

from abc import ABCMeta
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any, Generic, IO, TypeVar
import yaml
from rechu.models import Base

T = TypeVar('T', bound=Base)

class Reader(Generic[T], metaclass=ABCMeta):
    """
    File reader.
    """

    _mode = 'r'
    _encoding = 'utf-8'

    def __init__(self, path: Path, updated: datetime = datetime.min):
        self._path = path
        self._updated = updated

    def read(self) -> Iterator[T]:
        """
        Read the file from the path and yield specific models from it.
        """

        with self._path.open(self._mode, encoding=self._encoding) as file:
            yield from self.parse(file)

    def parse(self, file: IO) -> Iterator[T]:
        """
        Parse an open file and yield specific models from it.
        """

        raise NotImplementedError('Must be implemented by subclasses')

class YAMLReader(Reader[T], metaclass=ABCMeta):
    """
    YAML file reader.
    """

    def load(self, file: IO) -> Any:
        """
        Load the YAML file as a Python value.
        """

        return yaml.safe_load(file)

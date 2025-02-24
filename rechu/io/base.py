"""
Abstract base classes for file reading, writing and parsing.
"""

from abc import ABCMeta
from collections.abc import Iterator
from datetime import datetime
import os
from pathlib import Path
from typing import Any, Generic, IO, Optional, TypeVar
import yaml
from rechu.models.base import Base, Price

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

class Writer(Generic[T], metaclass=ABCMeta):
    """
    File writer.
    """

    _mode = 'w'
    _encoding = 'utf-8'

    def __init__(self, path: Path, model: T,
                 updated: Optional[datetime] = None):
        self._path = path
        self._model = model
        self._updated = updated

    def write(self) -> None:
        """
        Write the model to the path.
        """

        with self._path.open(self._mode, encoding=self._encoding) as file:
            self.serialize(file)

        if self._updated is not None:
            os.utime(self._path, times=(self._updated.timestamp(),
                                        self._updated.timestamp()))

    def serialize(self, file: IO) -> None:
        """
        Write a serialized variant of the model to the open file.
        """

        raise NotImplementedError('Must be implemented by subclasses')

class YAMLWriter(Writer[T], metaclass=ABCMeta):
    """
    YAML file writer.
    """

    @staticmethod
    def _represent_price(dumper: yaml.Dumper, data: Price) -> yaml.Node:
        return dumper.represent_scalar('tag:yaml.org,2002:float', str(data))

    def save(self, data: Any, file: IO) -> None:
        """
        Save the YAML file from a Python value.
        """

        yaml.add_representer(Price, self._represent_price)
        yaml.dump(data, file, width=80, indent=2, default_flow_style=None,
                  sort_keys=False)

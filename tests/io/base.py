"""
Tests for abstract base classes for file reading, writing and parsing.
"""

from io import StringIO
from pathlib import Path
import unittest
from rechu.io.base import Reader, Writer
from .. import concrete
from ..models.base import TestEntity

class TestReader(Reader[TestEntity]):
    """
    Test reader.
    """

    parse = concrete(Reader[TestEntity].parse)

class TestWriter(Writer[TestEntity]):
    """
    Test writer.
    """

    serialize = concrete(Writer[TestEntity].serialize)

# mypy: disable-error-code="abstract"
class ReaderTest(unittest.TestCase):
    """
    Tests for file reader.
    """

    def setUp(self) -> None:
        self.reader = TestReader(Path('samples/receipt.yml'))

    def test_path(self) -> None:
        """
        Test retrieving the path from which to read the models.
        """

        self.assertEqual(self.reader.path,
                         Path('samples/receipt.yml'))

    def test_read(self) -> None:
        """
        Test reading the file from the path and yielding models.
        """

        with self.assertRaises(NotImplementedError):
            next(self.reader.read())

    def test_parse(self) -> None:
        """
        Test parsing an open file.
        """

        with self.assertRaises(NotImplementedError):
            self.reader.parse(StringIO(''))

class WriterTest(unittest.TestCase):
    """
    Tests for file writer.
    """

    def setUp(self) -> None:
        path = Path('samples/entity.yml')
        models = (TestEntity(),)
        self.writer = TestWriter(path, models)

    def test_path(self) -> None:
        """
        Test retrieving the path to which to write the models.
        """

        self.assertEqual(self.writer.path, Path('samples/entity.yml'))

    def test_serialize(self) -> None:
        """
        Test writing a serialized variant of a model to an open file.
        """

        with self.assertRaises(NotImplementedError):
            self.writer.serialize(StringIO(''))

"""
Tests for abstract base classes for file reading, writing and parsing.
"""

from io import StringIO
import os
from pathlib import Path
import unittest
from rechu.io.base import Reader, Writer
from rechu.models import Base

class ReaderTest(unittest.TestCase):
    """
    Tests for file reader.
    """

    def test_path(self) -> None:
        """
        Test retrieving the path from which to read the models.
        """

        self.assertEqual(Reader(Path('samples/receipt.yml')).path,
                         Path('samples/receipt.yml'))

    def test_read(self) -> None:
        """
        Test reading the file from the path and yielding models.
        """

        with self.assertRaises(NotImplementedError):
            next(Reader(Path('samples/receipt.yml')).read())

    def test_parse(self) -> None:
        """
        Test parsing an open file.
        """

        with self.assertRaises(NotImplementedError):
            Reader(Path('fake/file')).parse(StringIO(''))

class WriterTest(unittest.TestCase):
    """
    Tests for file writer.
    """

    def test_path(self) -> None:
        """
        Test retrieving the path to which to write the models.
        """

        self.assertEqual(Writer(Path('samples/receipt.yml'), (Base(),)).path,
                         Path('samples/receipt.yml'))

    def test_write(self) -> None:
        """
        Test writing the model to the path.
        """

        with self.assertRaises(NotImplementedError):
            Writer(Path(os.devnull), (Base(),)).write()

    def test_serialize(self) -> None:
        """
        Test writing a serialized variant of a model to an open file.
        """

        with self.assertRaises(NotImplementedError):
            Writer(Path('fake/file'), (Base(),)).serialize(StringIO(''))

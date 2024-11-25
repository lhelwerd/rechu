"""
Tests for abstract base classes for file reading, writing and parsing.
"""

from io import StringIO
from pathlib import Path
import unittest
from rechu.io.base import Reader

class ReaderTest(unittest.TestCase):
    """
    Tests for file reader.
    """

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

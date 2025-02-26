"""
Tests of subcommand to export database entries as YAML files.
"""

from datetime import datetime
from itertools import zip_longest
import os
from pathlib import Path
import shutil
from unittest.mock import patch
from rechu.command.dump import Dump
from rechu.io.receipt import ReceiptReader
from ..database import DatabaseTestCase

class DumpTest(DatabaseTestCase):
    """
    Test dumping YAML files from the database.
    """

    path = Path("tmp")
    copy = Path("samples/receipt-1.yml")

    def tearDown(self) -> None:
        super().tearDown()
        shutil.rmtree(self.path, ignore_errors=True)
        self.copy.unlink(missing_ok=True)

    @patch.dict('os.environ', {'RECHU_DATA_PATH': 'tmp'})
    def test_run(self) -> None:
        """
        Test executing the command.
        """

        path = Path("samples/receipt.yml").resolve()
        now = datetime.now()

        with self.database as session:
            session.add(next(ReceiptReader(path, updated=now).read()))
            self.copy.symlink_to(path.name)
            self.assertEqual(self.copy.resolve(), path)
            session.add(next(ReceiptReader(self.copy, updated=now).read()))

        command = Dump()
        command.run()

        # The original filename is preferred over the date format.
        dump_path = self.path / "samples" / "receipt.yml"
        copy_path = self.path / "samples" / "receipt-1.yml"
        self.assertTrue(dump_path.exists())
        self.assertTrue(copy_path.exists())

        with path.open("r", encoding="utf-8") as source_file:
            with dump_path.open("r", encoding="utf-8") as dump_file:
                for (line, (source, dump)) in enumerate(zip_longest(source_file,
                                                                    dump_file)):
                    with self.subTest(line=line):
                        self.assertEqual(source.replace(", other", ""), dump)

        os.utime(dump_path, times=(now.timestamp() + 1, now.timestamp() + 1))

        command = Dump()
        command.files = ["receipt.yml"]
        command.run()

        # Existing file is not overridden or has its modification date changed.
        self.assertEqual(dump_path.stat().st_mtime, now.timestamp() + 1)
        self.assertEqual(copy_path.stat().st_mtime, now.timestamp())

        command = Dump()
        command.files = ["2025-02-31-12-34-mia.yml"]
        command.run()

        missing_path = self.path / "samples" / "2025-02-31-12-34-mia.yml"
        self.assertFalse(missing_path.exists())

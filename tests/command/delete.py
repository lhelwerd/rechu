"""
Tests of subcommand to remove receipt YAML files and database entries.
"""

from pathlib import Path
from typing import final
from sqlalchemy import select
from typing_extensions import override
from rechu.command.delete import Delete
from rechu.io.receipt import ReceiptReader
from rechu.models.receipt import Receipt, DiscountItems, ProductItem, Discount
from ..database import DatabaseTestCase

@final
class DeleteTest(DatabaseTestCase):
    """
    Test deleting YAML files and database entries for receipts.
    """

    copies = [Path("samples/receipt-1.yml"), Path("samples/receipt-2.yml")]

    @override
    def tearDown(self) -> None:
        super().tearDown()
        for copy in self.copies:
            copy.unlink(missing_ok=True)

    def test_run(self) -> None:
        """
        Test executing the command.
        """

        path = Path("samples/receipt.yml").resolve()

        with self.database as session:
            session.add(next(ReceiptReader(path).read()))

        command = Delete()
        command.files = [str(path)]
        command.keep = True
        command.run()

        with self.database as session:
            self.assertIsNone(session.scalars(select(Receipt)).first())
            self.assertIsNone(session.scalars(select(ProductItem)).first())
            self.assertIsNone(session.scalars(select(Discount)).first())
            self.assertIsNone(session.scalars(select(DiscountItems)).first())

        with self.database as session:
            session.add(next(ReceiptReader(path).read()))
            for copy in self.copies:
                copy.symlink_to(path.name)
                self.assertEqual(copy.resolve(), path)
                session.add(next(ReceiptReader(copy).read()))

        command.files = ["receipt-1.yml", "receipt-2.yml", "missing.yml"]
        command.keep = False
        command.run()

        with self.database as session:
            receipts = list(session.scalars(select(Receipt)))
            self.assertEqual(len(receipts), 1)
            self.assertEqual(receipts[0].filename, 'receipt.yml')

        self.assertTrue(path.exists())
        for copy in self.copies:
            self.assertFalse(copy.exists())

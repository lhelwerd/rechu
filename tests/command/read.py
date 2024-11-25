"""
Tests of subcommand to import receipt YAML files.
"""

from datetime import datetime
import os
from sqlalchemy import select
from rechu.command.read import Read
from rechu.database import Database
from rechu.models import Base, Receipt
from ..settings import SettingsTestCase

class ReadTest(SettingsTestCase):
    """
    Test reading the YAML files and importing them to the database.
    """

    def tearDown(self) -> None:
        with Database() as session:
            Base.metadata.drop_all(session.get_bind())

    def test_run(self) -> None:
        """
        Test executing the command.
        """

        with Database() as session:
            Base.metadata.create_all(session.get_bind())

        now = datetime.now().timestamp()
        os.utime('samples', times=(now, now))
        os.utime('samples/receipt.yml', times=(now, now))

        command = Read()
        command.run()

        with Database() as session:
            receipt = session.scalars(select(Receipt)).first()
            if receipt is None:
                self.fail("Expected receipt to be stored")
            self.assertEqual(receipt.filename, 'receipt.yml')
            updated = receipt.updated

        # Nothing happens if the directory is not updated.
        command.run()

        with Database() as session:
            receipt = session.scalars(select(Receipt)).first()
            if receipt is None:
                self.fail("Expected receipt to be stored")
            self.assertEqual(receipt.filename, 'receipt.yml')
            self.assertEqual(receipt.updated, updated)

        os.utime('samples', times=(now + 1, now + 1))

        # Nothing happens if the file is not updated.
        command.run()

        with Database() as session:
            receipt = session.scalars(select(Receipt)).first()
            if receipt is None:
                self.fail("Expected receipt to be stored")
            self.assertEqual(receipt.filename, 'receipt.yml')
            self.assertEqual(receipt.updated, updated)

        os.utime('samples/receipt.yml', times=(now + 1, now + 1))
        command.run()

        with Database() as session:
            receipt = session.scalars(select(Receipt)).first()
            if receipt is None:
                self.fail("Expected receipt to be stored")
            self.assertEqual(receipt.filename, 'receipt.yml')
            self.assertNotEqual(receipt.updated, updated)

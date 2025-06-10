"""
Subcommand to export database entries as YAML files.
"""

from pathlib import Path
from typing import TypeVar
from sqlalchemy import select
from sqlalchemy.orm import Session
from .base import Base
from ..database import Database
from ..inventory.base import Selectors
from ..inventory.products import Products
from ..io.base import Writer
from ..io.receipt import ReceiptWriter
from ..models import Base as ModelBase, Receipt

T = TypeVar('T', bound=ModelBase)

@Base.register("dump")
class Dump(Base):
    """
    Dump YAML files from the database.
    """

    subparser_keywords = {
        'help': 'Export entities from the database',
        'description': 'Create one or more YAML files for data in the database.'
    }
    subparser_arguments = [
        ('files', {
            'metavar': 'FILE',
            'nargs': '*',
            'help': 'One or more product inventories or receipts to write; if '
                    'no filenames are given, then the entire database is dumped'
        })
    ]

    def __init__(self) -> None:
        super().__init__()
        self.files: list[str] = []
        self.data_path = Path(self.settings.get('data', 'path'))
        self._directories: set[Path] = set()

    def run(self) -> None:
        products_pattern = Products.get_parts(self.settings)[-1]

        products_files: Selectors = []
        receipt_files: list[str] = []
        for file in self.files:
            products_match = products_pattern.match(file)
            if products_match:
                products_files.append(products_match.groupdict())
            else:
                # Filter off path elements to just keep the file name
                receipt_files.append(Path(file).name)

        with Database() as session:
            self._write_products(session, products_files)
            self._write_receipts(session, receipt_files)

    def _write_products(self, session: Session, files: Selectors) -> None:
        for writer in Products.select(session, selectors=files).get_writers():
            self._write(writer)

    def _write_receipts(self, session: Session, files: list[str]) -> None:
        data_format = self.settings.get('data', 'format')

        receipts = select(Receipt)
        if files:
            receipts = receipts.where(Receipt.filename.in_(files))
        for receipt in session.scalars(receipts):
            path_format = self.data_path / data_format.format(date=receipt.date,
                                                              shop=receipt.shop)
            path = path_format.parent / receipt.filename
            self._write(ReceiptWriter(path, (receipt,)))

    def _write(self, writer: Writer[T]) -> None:
        # Only write new files, do not overwrite existing ones
        path = writer.path
        if not path.exists():
            if path.parent not in self._directories:
                # Create directories when needed, cache directories
                path.parent.mkdir(parents=True, exist_ok=True)
                self._directories.add(path.parent)

            writer.write()

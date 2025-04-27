"""
Subcommand to export database entries as YAML files.
"""

import logging
from pathlib import Path
import re
from string import Formatter
from typing import Collection, Optional, TypeVar
from sqlalchemy import select
from sqlalchemy.orm import Session
from .base import Base
from ..database import Database
from ..io.base import YAMLWriter
from ..io.products import ProductsWriter
from ..io.receipt import ReceiptWriter
from ..models import Base as ModelBase, Product, Receipt

_ProductParts = tuple[str, ...]
_ProductFiles = list[dict[str, Optional[str]]]

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

    def _get_products_parts(self) -> tuple[str, _ProductParts, re.Pattern[str]]:
        formatter = Formatter()
        path_format = self.settings.get('data', 'products')
        parts = list(formatter.parse(path_format))
        fields = tuple(part[1] for part in parts if part[1] is not None)
        path = ''.join(rf"{re.escape(part[0])}(?P<{part[1]}>.*)??"
                       if part[1] is not None else re.escape(part[0])
                       for part in parts)
        pattern = re.compile(rf"(^|.*/){path}$")
        return path_format, fields, pattern

    def run(self) -> None:
        products_format, products_fields, products_pattern = \
            self._get_products_parts()
        logging.warning('Products fields: %r', products_fields)
        logging.warning('Products pattern: %s', products_pattern)

        products_files: _ProductFiles = []
        receipt_files: list[str] = []
        for file in self.files:
            products_match = products_pattern.match(file)
            if products_match:
                products_files.append(products_match.groupdict())
            else:
                # Filter off path elements to just keep the file name
                receipt_files.append(Path(file).name)

        with Database() as session:
            self._write_products(session, products_format, products_fields,
                                 products_files)

            self._write_receipts(session, receipt_files)

    def _write_products(self, session: Session, path_format: str,
                        parts: _ProductParts, files: _ProductFiles) -> None:
        if not files:
            query = select(*(getattr(Product, field) for field in parts)) \
                .distinct()
            files = [
                dict(zip(parts, values)) for values in session.execute(query)
            ]
            logging.warning('Products files fields: %r', files)

        for fields in files:
            products = session.scalars(select(Product).filter_by(**fields)).all()
            path = self.data_path / Path(path_format.format(**fields))
            self._write(ProductsWriter, path, products)

    def _write_receipts(self, session: Session, files: list[str]) -> None:
        data_format = self.settings.get('data', 'format')

        receipts = select(Receipt)
        if files:
            receipts = receipts.where(Receipt.filename.in_(files))
        for receipt in session.scalars(receipts):
            path_format = self.data_path / data_format.format(date=receipt.date,
                                                              shop=receipt.shop)
            path = path_format.parent / receipt.filename
            self._write(ReceiptWriter, path, (receipt,))

    def _write(self, writer_class: type[YAMLWriter[T]], path: Path,
               models: Collection[T]) -> None:
        # Only write new files, do not overwrite existing ones
        if not path.exists():
            if path.parent not in self._directories:
                # Create directories when needed, cache directories
                path.parent.mkdir(parents=True, exist_ok=True)
                self._directories.add(path.parent)

            writer = writer_class(path, models)
            writer.write()

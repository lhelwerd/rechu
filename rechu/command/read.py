"""
Subcommand to import receipt YAML files.
"""

from datetime import datetime
import logging
import re
from pathlib import Path
from string import Formatter
from sqlalchemy import select
from sqlalchemy.orm import Session
from .base import Base
from ..database import Database
from ..io.receipt import ReceiptReader
from ..models import Receipt

def get_updated_time(path: Path) -> datetime:
    """
    Retrieve the latest modification time of a file or directory in the `path`
    as a `datetime` object.
    """

    return datetime.fromtimestamp(path.stat().st_mtime)

@Base.register("read")
class Read(Base):
    """
    Read updated YAML files and import them to the database.
    """

    subparser_keywords = {
        'help': 'Import updated receipt files to the database',
        'description': 'Find YAML files for receipts from the data paths and '
                       'import new or updated files to the database.'
    }

    def run(self) -> None:
        data_path = Path(self.settings.get('data', 'path'))
        data_pattern = self.settings.get('data', 'pattern')

        formatter = Formatter()
        products_parts = formatter.parse(self.settings.get('data', 'products'))
        products_path = '.*'.join(re.escape(part[0]) for part in products_parts)
        products = re.compile(rf"(^|.*/){products_path}$")
        logging.warning("Products pattern: %r", products)

        with Database() as session:
            receipts = {
                receipt.filename: receipt.updated
                for receipt in session.scalars(select(Receipt))
            }
            latest = max(receipts.values(), default=datetime.min)
            directories = [data_path] if data_pattern == '.' else \
                data_path.glob(data_pattern)
            logging.warning('Latest timestamp in DB: %s', latest)
            for data_directory in directories:
                if data_directory.is_dir() and \
                    get_updated_time(data_directory) >= latest:
                    logging.warning('Looking at files in %s', data_directory)
                    self._handle_directory(data_directory, receipts, session,
                                           products)

    def _handle_directory(self, data_directory: Path,
                          receipts: dict[str, datetime],
                          session: Session, products: re.Pattern) -> None:
        for path in data_directory.glob('*.yml'):
            if products.match(str(path)):
                continue
            if self._is_updated(path, receipts):
                try:
                    receipt = next(ReceiptReader(path,
                                                 updated=datetime.now()).read())
                    if receipt.filename in receipts:
                        session.merge(receipt)
                    else:
                        session.add(receipt)
                except (StopIteration, TypeError):
                    logging.exception('Could not retrieve receipt %s', path)

    @staticmethod
    def _is_updated(receipt_path: Path, receipts: dict[str, datetime]) -> bool:
        if receipt_path.name not in receipts:
            return True

        updated = get_updated_time(receipt_path)
        return updated >= receipts[receipt_path.name]

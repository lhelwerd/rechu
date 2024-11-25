"""
Subcommand to import receipt YAML files.
"""

from datetime import datetime
import logging
from pathlib import Path
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

    def run(self) -> None:
        data_path = Path(self.settings.get('data', 'path'))
        data_pattern = self.settings.get('data', 'pattern')
        with Database() as session:
            receipts = {
                receipt.filename: receipt.updated
                for receipt in session.scalars(select(Receipt))
            }
            latest = max(receipts.values(), default=datetime.min)
            directories = [data_path] if data_pattern == '.' else \
                data_path.glob(data_pattern)
            logging.warning('Latest timestamp in DB: %s', latest)
            for receipt_directory in directories:
                if receipt_directory.is_dir() and \
                    get_updated_time(receipt_directory) >= latest:
                    logging.warning('Looking at files in %s', receipt_directory)
                    self._handle_directory(receipt_directory, receipts, session)

    def _handle_directory(self, receipt_directory: Path,
                          receipts: dict[str, datetime],
                          session: Session) -> None:
        for receipt_path in receipt_directory.glob('*.yml'):
            if self._is_updated(receipt_path, receipts):
                try:
                    receipt = next(ReceiptReader(receipt_path,
                                                 updated=datetime.now()).read())
                    if receipt.filename in receipts:
                        session.merge(receipt)
                    else:
                        session.add(receipt)
                except (StopIteration, TypeError):
                    logging.exception('Could not retrieve receipt %s',
                                      receipt_path)

    @staticmethod
    def _is_updated(receipt_path: Path, receipts: dict[str, datetime]) -> bool:
        if receipt_path.name not in receipts:
            return True

        updated = get_updated_time(receipt_path)
        return updated >= receipts[receipt_path.name]

"""
Subcommand to import receipt YAML files.
"""

from collections.abc import Hashable
from datetime import datetime
from itertools import chain
import logging
import re
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import Session
from .base import Base
from ..database import Database
from ..inventory.products import Products
from ..io.products import ProductsReader
from ..io.receipt import ReceiptReader
from ..matcher.product import ProductMatcher
from ..models import Receipt

_ProductMap = dict[str, dict[Hashable, int]]

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
        'help': 'Import updated product and receipt files to the database',
        'description': 'Find YAML files for products and receipts stored in '
                       'the data paths and import new or updated entities to '
                       'the database.'
    }
    def run(self) -> None:
        data_path = Path(self.settings.get('data', 'path'))

        matcher = ProductMatcher()

        with Database() as session:
            products = Products.select(session)
            _, products_glob, _, products_pattern = \
                Products.get_parts(self.settings)
            matcher.fill_map(products)
            self._handle_products(session, data_path, matcher, products_glob)
            session.flush()
            new_receipts = self._handle_receipts(session, data_path,
                                                 products_pattern)
            self._update_matches(session, new_receipts)

    def _handle_products(self, session: Session, data_path: Path,
                         matcher: ProductMatcher, products_glob: str) -> None:
        for path in sorted(data_path.glob(products_glob)):
            logging.warning('Looking at products in %s', path)
            with path.open('r', encoding='utf-8') as file:
                try:
                    for product in ProductsReader(path).parse(file):
                        existing = matcher.check_map(product)
                        if existing is None:
                            session.add(product)
                        else:
                            product.id = existing.id
                            session.merge(product)
                except (TypeError, ValueError):
                    logging.exception('Could not parse product from %s', path)

    def _handle_receipts(self, session: Session, data_path: Path,
                         products_pattern: re.Pattern[str]) -> list[Receipt]:
        data_pattern = self.settings.get('data', 'pattern')

        receipts = {
            receipt.filename: receipt.updated
            for receipt in session.scalars(select(Receipt))
        }
        new_receipts: list[Receipt] = []

        latest = max(receipts.values(), default=datetime.min)
        directories = [data_path] if data_pattern == '.' else \
            data_path.glob(data_pattern)
        logging.warning('Latest timestamp in DB: %s', latest)
        for data_directory in directories:
            if data_directory.is_dir() and \
                get_updated_time(data_directory) >= latest:
                logging.warning('Looking at files in %s', data_directory)
                new_receipts.extend(self._handle_directory(data_directory,
                                                           receipts, session,
                                                           products_pattern))

        return new_receipts

    def _handle_directory(self, data_directory: Path,
                          receipts: dict[str, datetime],
                          session: Session,
                          products_pattern: re.Pattern) -> list[Receipt]:
        new_receipts: list[Receipt] = []
        for path in data_directory.glob('*.yml'):
            if products_pattern.match(str(path)):
                continue
            if self._is_updated(path, receipts):
                try:
                    receipt = next(ReceiptReader(path,
                                                 updated=datetime.now()).read())
                    if receipt.filename in receipts:
                        receipt = session.merge(receipt)
                    else:
                        session.add(receipt)
                    new_receipts.append(receipt)
                except (StopIteration, TypeError):
                    logging.exception('Could not retrieve receipt %s', path)

        return new_receipts

    @staticmethod
    def _is_updated(receipt_path: Path, receipts: dict[str, datetime]) -> bool:
        if receipt_path.name not in receipts:
            return True

        updated = get_updated_time(receipt_path)
        return updated >= receipts[receipt_path.name]

    def _update_matches(self, session: Session,
                        receipts: list[Receipt]) -> None:
        matcher = ProductMatcher()
        items = list(chain(*(receipt.products for receipt in receipts)))
        pairs = matcher.find_candidates(session, items, only_unmatched=True)
        for product, item in matcher.filter_duplicate_candidates(pairs):
            logging.warning('Matching %r with %r', item, product)
            item.product = product

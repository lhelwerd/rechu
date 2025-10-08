"""
Subcommand to import receipt YAML files.
"""

from collections.abc import Hashable
from datetime import datetime
from itertools import chain
import re
from pathlib import Path
from typing import final
from typing_extensions import override
from sqlalchemy import select
from sqlalchemy.orm import Session
from .base import Base
from ..database import Database
from ..inventory import Inventory
from ..inventory.products import Products
from ..inventory.shops import Shops
from ..io.products import ProductsReader
from ..io.receipt import ReceiptReader
from ..matcher.product import ProductMatcher
from ..models import Receipt, Shop

_ProductMap = dict[str, dict[Hashable, int]]

def get_updated_time(path: Path) -> datetime:
    """
    Retrieve the latest modification time of a file or directory in the `path`
    as a `datetime` object.
    """

    return datetime.fromtimestamp(path.stat().st_mtime)

@final
@Base.register("read")
class Read(Base):
    """
    Read updated YAML files and import them to the database.
    """

    subparser_keywords = {
        'help': 'Import updated product and receipt files to the database',
        'description': ('Find YAML files for products and receipts stored in '
                        'the data paths and import new or updated entities to '
                        'the database.')
    }

    def __init__(self) -> None:
        super().__init__()
        self.shops: Inventory[Shop] = Shops()

    @override
    def run(self) -> None:
        data_path = Path(self.settings.get('data', 'path'))

        with Database() as session:
            self._handle_shops(session)

            _, products_glob, _, products_pattern = \
                Products.get_parts(self.settings)
            self._handle_products(session, data_path, products_glob)
            session.flush()
            new_receipts = self._handle_receipts(session, data_path,
                                                 products_pattern)
            self._update_matches(session, new_receipts)

    def _handle_shops(self, session: Session) -> None:
        self.shops = Shops.select(session)
        new_shops = self.shops.merge_update(Shops.read()).values()
        for shops in new_shops:
            for shop in shops:
                _ = shop.merge(session.merge(shop))
        if new_shops:
            session.flush()
            self.shops = Shops.select(session)

    def _handle_products(self, session: Session, data_path: Path,
                         products_glob: str) -> None:
        matcher = ProductMatcher()
        products = Products.select(session)
        matcher.fill_map(products)
        unseen = set(chain(*products.values()))

        for path in sorted(data_path.glob(products_glob)):
            self.logger.info('Looking at products in %s', path)
            try:
                for product in ProductsReader(path).read():
                    product.shop_meta = self.shops.find(product.shop)
                    existing = matcher.check_map(product)
                    if existing is None:
                        session.add(product)
                    else:
                        unseen.discard(existing)
                        if existing.merge(product):
                            product.id = existing.id
                            _ = session.merge(product)
            except (TypeError, ValueError):
                self.logger.exception('Could not parse product from %s', path)

        for removed in unseen:
            self.logger.warning('Deleting %r from database', removed)
            session.delete(removed)

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
        self.logger.info('Latest update timestamp in DB: %s', latest)
        for data_directory in directories:
            # Look at directories with recent files (not strictly updated
            # because multiple files may have the same updated time)
            if data_directory.is_dir() and \
                get_updated_time(data_directory) >= latest:
                self.logger.info('Looking at files in %s', data_directory)
                new_receipts.extend(self._handle_directory(data_directory,
                                                           receipts, session,
                                                           products_pattern))

        return new_receipts

    def _handle_directory(self, data_directory: Path,
                          receipts: dict[str, datetime],
                          session: Session,
                          products_pattern: re.Pattern[str]) -> list[Receipt]:
        new_receipts: list[Receipt] = []
        for path in data_directory.glob('*.yml'):
            if products_pattern.match(str(path)):
                continue
            if self._is_updated(path, receipts):
                try:
                    receipt = next(ReceiptReader(path,
                                                 updated=datetime.now()).read())
                    receipt.shop_meta = self.shops.find(receipt.shop)
                    if receipt.filename in receipts:
                        receipt = session.merge(receipt)
                    else:
                        session.add(receipt)
                    new_receipts.append(receipt)
                except (StopIteration, TypeError):
                    self.logger.exception('Could not retrieve receipt %s', path)

        return new_receipts

    @staticmethod
    def _is_updated(receipt_path: Path, receipts: dict[str, datetime]) -> bool:
        if receipt_path.name not in receipts:
            return True

        updated = get_updated_time(receipt_path)
        # Check if the updated time is stricly newer
        return updated > receipts[receipt_path.name]

    def _update_matches(self, session: Session,
                        receipts: list[Receipt]) -> None:
        matcher = ProductMatcher()
        items = list(chain(*(receipt.products for receipt in receipts)))
        pairs = matcher.find_candidates(session, items, only_unmatched=True)
        for product, item in matcher.filter_duplicate_candidates(pairs):
            self.logger.info('Matching %r with %r', item, product)
            item.product = product

"""
Subcommand to import receipt YAML files.
"""

from collections.abc import Hashable
from datetime import datetime
import glob
import logging
import re
from pathlib import Path
from string import Formatter
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from .base import Base
from ..database import Database
from ..io.products import ProductsReader
from ..io.receipt import ReceiptReader
from ..models import Product, Receipt

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

        products_glob, products_pattern = self._get_products_patterns()
        logging.info("Products glob: %s/%s", data_path, products_glob)
        logging.info("Products pattern: %r", products_pattern)

        with Database() as session:
            self._handle_products(session, data_path, products_glob)
            self._handle_receipts(session, data_path, products_pattern)

    def _get_products_patterns(self) -> tuple[str, re.Pattern[str]]:
        formatter = Formatter()
        parts = list(formatter.parse(self.settings.get('data', 'products')))
        glob_pattern = '*'.join(glob.escape(part[0]) for part in parts)
        path = '.*'.join(re.escape(part[0]) for part in parts)
        re_pattern = re.compile(rf"(^|.*/){path}$")
        return glob_pattern, re_pattern

    def _handle_products(self, session: Session, data_path: Path,
                         products_glob: str) -> None:
        products = self._get_products_map(session)
        for path in data_path.glob(products_glob):
            logging.warning('Looking at products in %s', path)
            with path.open('r', encoding='utf-8') as file:
                try:
                    for product in ProductsReader(path).parse(file):
                        product_id = self._check_products_map(products, product)
                        if product_id is None:
                            session.add(product)
                        else:
                            product.id = product_id
                            session.merge(product)
                except (TypeError, ValueError):
                    logging.exception('Could not parse product from %s', path)

    @staticmethod
    def _get_product_match(product: Product) -> Hashable:
        return (
            tuple(label.name for label in product.labels),
            tuple(
                (price.indicator, price.value)
                for price in product.prices
            ),
            tuple(discount.label for discount in product.discounts)
        )

    def _get_products_map(self, session: Session) -> _ProductMap:
        products: _ProductMap = {
            'match': {},
            'sku': {},
            'gtin': {}
        }
        for product in session.scalars(select(Product)):
            match = self._get_product_match(product)
            products['match'][match] = product.id
            if product.sku is not None:
                products['sku'][(product.shop, product.sku)] = product.id
            if product.gtin is not None:
                products['gtin'][product.gtin] = product.id

        return products

    def _check_products_map(self, products: _ProductMap,
                            product: Product) -> Optional[int]:
        match = self._get_product_match(product)
        if match in products['match']:
            return products['match'][match]
        if (product.shop, product.sku) in products['sku']:
            return products['sku'][(product.shop, product.sku)]
        if product.gtin in products['gtin']:
            return products['gtin'][product.gtin]
        return None

    def _handle_receipts(self, session: Session, data_path: Path,
                         products_pattern: re.Pattern[str]) -> None:
        data_pattern = self.settings.get('data', 'pattern')

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
                                       products_pattern)

    def _handle_directory(self, data_directory: Path,
                          receipts: dict[str, datetime],
                          session: Session,
                          products_pattern: re.Pattern) -> None:
        for path in data_directory.glob('*.yml'):
            if products_pattern.match(str(path)):
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

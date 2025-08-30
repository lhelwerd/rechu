"""
Products inventory.
"""

from collections.abc import Hashable, Iterable, Iterator, Sequence
import glob
import logging
from pathlib import Path
import re
from string import Formatter
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from .base import Inventory, Selectors
from ..io.products import ProductsReader, ProductsWriter, SharedFields, \
    SHARED_FIELDS
from ..matcher.product import ProductMatcher
from ..models.product import Product
from ..settings import Settings

LOGGER = logging.getLogger(__name__)

class Products(dict, Inventory[Product]):
    """
    Inventory of products grouped by their identifying fields.
    """

    def __init__(self, mapping = None, /, parts: Optional[SharedFields] = None):
        super().__init__()
        if mapping is not None:
            self.update(mapping)
        if parts is None:
            settings = Settings.get_settings()
            parts = self.get_parts(settings)[2]
        self._parts = set(parts)
        self._matcher = ProductMatcher()

    @staticmethod
    def get_parts(settings: Settings) \
            -> tuple[str, str, SharedFields, re.Pattern[str]]:
        """
        Retrieve various formatting, selecting and matching parts for inventory
        filenames of products.
        """

        formatter = Formatter()
        path_format = settings.get('data', 'products')
        prefixes, keys, _, _ = zip(*formatter.parse(path_format))
        glob_pattern = '*'.join(glob.escape(prefix) for prefix in prefixes)
        fields = tuple(key for key in keys if key in SHARED_FIELDS)
        path = ''.join(rf"{re.escape(prefix)}(?P<{key}>.*)??"
                       if key is not None else re.escape(prefix)
                       for prefix, key in zip(prefixes, keys))
        pattern = re.compile(rf"(^|.*/){path}$")
        return path_format, glob_pattern, fields, pattern

    @classmethod
    def spread(cls, models: Iterable[Product]) -> "Inventory[Product]":
        inventory: dict[Path, list[Product]] = {}
        settings = Settings.get_settings()
        data_path = settings.get('data', 'path')
        path_format, _, parts, _ = cls.get_parts(settings)
        for model in models:
            fields = {str(part): getattr(model, part) for part in parts}
            path = data_path / Path(path_format.format(**fields))
            inventory.setdefault(path.resolve(), [])
            inventory[path.resolve()].append(model)

        return cls(inventory, parts=parts)

    @classmethod
    def select(cls, session: Session,
               selectors: Optional[Selectors] = None) -> "Inventory[Product]":
        inventory: dict[Path, Sequence[Product]] = {}
        settings = Settings.get_settings()
        data_path = settings.get('data', 'path')
        path_format, _, parts, _ = cls.get_parts(settings)
        if not parts:
            selectors = [{}]
        elif not selectors:
            query = select(*(getattr(Product, field) for field in parts)) \
                .distinct()
            selectors = [
                dict(zip(parts, values)) for values in session.execute(query)
            ]
            LOGGER.debug('Products files fields: %r', selectors)

        for fields in selectors:
            products = session.scalars(select(Product)
                                       .filter(Product.generic_id.is_(None))
                                       .filter_by(**fields)).all()
            path = data_path / Path(path_format.format(**fields))
            inventory[path.resolve()] = products

        return cls(inventory, parts=parts)

    @classmethod
    def read(cls) -> "Inventory[Product]":
        inventory: dict[Path, Sequence[Product]] = {}
        settings = Settings.get_settings()
        data_path = Path(settings.get('data', 'path'))
        _, glob_pattern, parts, _ = cls.get_parts(settings)
        for path in sorted(data_path.glob(glob_pattern)):
            LOGGER.info('Looking at products in %s', path)
            try:
                products = list(ProductsReader(path).read())
                inventory[path.resolve()] = products
            except (TypeError, ValueError):
                LOGGER.exception('Could not parse product from %s', path)

        return cls(inventory, parts=parts)

    def get_writers(self) -> Iterator[ProductsWriter]:
        for path, products in self.items():
            yield ProductsWriter(path, products, shared_fields=self._parts)

    def _find_match(self, product: Product, update: bool = True,
                    only_new: bool = False) -> tuple[Optional[Product], bool]:
        changed = False
        existing = self._matcher.check_map(product)
        if existing is None:
            changed = True
            existing = product
        elif only_new:
            return None, False
        elif not update:
            existing = existing.copy()
        if existing.merge(product):
            changed = True
        return existing, changed

    def merge_update(self, other: "Inventory[Product]", update: bool = True,
                     only_new: bool = False) -> "Inventory[Product]":
        updated: dict[Path, list[Product]] = {}
        self._matcher.fill_map(self)
        if only_new:
            update = False
        for path, products in other.items():
            changed = False
            updates: list[Product] = []
            for product in products:
                match, change = self._find_match(product, update=update,
                                                 only_new=only_new)
                changed = changed or change
                if match is not None:
                    updates.append(match)

            if update:
                previous = list(self.get(path, []))
                self[path] = previous + [
                    change for change in updates if change not in previous
                ]
                # Make the updates follow the same order and have entire path
                updates = self[path].copy()
            if changed:
                updated[path] = updates

        return Products(updated, parts=self._parts)

    def find(self, key: Hashable, update_map: bool = False) -> Product:
        if update_map:
            self._matcher.fill_map(self)

        return self._matcher.find_map(key)

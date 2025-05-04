"""
Products inventory.
"""

from collections.abc import Iterable, Sequence
import glob
import logging
from pathlib import Path
import re
from string import Formatter
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from .base import Inventory, Selectors
from ..io.products import ProductsReader
from ..matcher.product import ProductMatcher
from ..models.product import Product
from ..settings import Settings

_Parts = tuple[str, ...]

class Products(dict, Inventory[Product]):
    """
    Inventory of products grouped by their identifying fields.
    """

    @staticmethod
    def get_parts(settings: Settings) \
            -> tuple[str, str, _Parts, re.Pattern[str]]:
        """
        Retrieve various formatting, selecting and matching parts for inventory
        filenames of products.
        """

        formatter = Formatter()
        path_format = settings.get('data', 'products')
        parts = list(formatter.parse(path_format))
        glob_pattern = '*'.join(glob.escape(part[0]) for part in parts)
        fields = tuple(part[1] for part in parts if part[1] is not None)
        path = ''.join(rf"{re.escape(part[0])}(?P<{part[1]}>.*)??"
                       if part[1] is not None else re.escape(part[0])
                       for part in parts)
        pattern = re.compile(rf"(^|.*/){path}$")
        return path_format, glob_pattern, fields, pattern

    @classmethod
    def spread(cls, models: Iterable[Product]) -> "Inventory[Product]":
        inventory: dict[Path, list[Product]] = {}
        settings = Settings.get_settings()
        data_path = settings.get('data', 'path')
        path_format, _, parts, _ = cls.get_parts(settings)
        for model in models:
            fields = {part: getattr(model, part) for part in parts}
            path = data_path / Path(path_format.format(**fields))
            inventory.setdefault(path.resolve(), [])
            inventory[path.resolve()].append(model)

        return cls(inventory)

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
            logging.warning('Products files fields: %r', selectors)

        for fields in selectors:
            products = session.scalars(select(Product)
                                       .filter_by(**fields)).all()
            path = data_path / Path(path_format.format(**fields))
            inventory[path.resolve()] = products

        return cls(inventory)

    @classmethod
    def read(cls) -> "Inventory[Product]":
        inventory: dict[Path, Sequence[Product]] = {}
        settings = Settings.get_settings()
        data_path = Path(settings.get('data', 'path'))
        glob_pattern = cls.get_parts(settings)[1]
        for path in sorted(data_path.glob(glob_pattern)):
            logging.warning('Looking at products in %s', path)
            with path.open('r', encoding='utf-8') as file:
                try:
                    products = list(ProductsReader(path).parse(file))
                    inventory[path.resolve()] = products
                except (TypeError, ValueError):
                    logging.exception('Could not parse product from %s', path)

        return cls(inventory)

    def merge_update(self, other: "Inventory[Product]") -> "Inventory[Product]":
        updated: dict[Path, list[Product]] = {}
        matcher = ProductMatcher()
        matcher.fill_map(self)
        for path, products in other.items():
            changed = False
            for product in products:
                existing = matcher.check_map(product)
                if existing is None:
                    existing = Product(shop=product.shop)
                    self[path] = list(self.get(path, [])) + [existing]
                if existing.merge(product):
                    changed = True
            if changed:
                updated[path] = self[path]

        return Products(updated)

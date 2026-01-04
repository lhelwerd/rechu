"""
Products inventory.
"""

import glob
import logging
import re
from collections.abc import Hashable, Iterable, Iterator
from pathlib import Path
from string import Formatter
from typing import TYPE_CHECKING, cast, final

from sqlalchemy import select
from sqlalchemy.orm import MappedColumn, Session
from typing_extensions import override

from ..io.products import (
    SHARED_FIELDS,
    ProductsReader,
    ProductsWriter,
    SharedFields,
)
from ..matcher.product import ProductMatcher
from ..models.product import Product
from ..settings import Settings
from .base import Inventory, Selectors

if TYPE_CHECKING:
    from _typeshed import SupportsKeysAndGetItem
else:
    SupportsKeysAndGetItem = dict

LOGGER = logging.getLogger(__name__)


@final
class Products(Inventory[Product], dict[Path, list[Product]]):
    """
    Inventory of products grouped by their identifying fields.
    """

    __getitem__ = dict[Path, list[Product]].__getitem__
    __iter__ = dict[Path, list[Product]].__iter__
    __len__ = dict[Path, list[Product]].__len__
    __hash__ = dict[Path, list[Product]].__hash__

    def __init__(
        self,
        mapping: SupportsKeysAndGetItem[Path, list[Product]] | None = None,
        /,
        parts: SharedFields | None = None,
    ) -> None:
        super().__init__()
        if mapping is not None:
            self.update(mapping)
        if parts is None:
            settings = Settings.get_settings()
            parts = self.get_parts(settings)[2]
        self._parts = set(parts)
        self._matcher = ProductMatcher()

    @staticmethod
    def get_parts(
        settings: Settings,
    ) -> tuple[str, str, SharedFields, re.Pattern[str]]:
        """
        Retrieve various formatting, selecting and matching parts for inventory
        filenames of products.
        """

        formatter = Formatter()
        path_format = settings.get("data", "products")
        prefixes: list[str] = []
        keys: list[str | None] = []
        for prefix, key, _, _ in formatter.parse(path_format):
            prefixes.append(prefix)
            keys.append(key)
        glob_pattern = "*".join(glob.escape(prefix) for prefix in prefixes)
        fields = cast(
            SharedFields, tuple(key for key in keys if key in SHARED_FIELDS)
        )
        path = "".join(
            rf"{re.escape(prefix)}(?P<{key}>.*)??"
            if key is not None
            else re.escape(prefix)
            for prefix, key in zip(prefixes, keys, strict=True)
        )
        pattern = re.compile(rf"(^|.*/){path}$")
        return path_format, glob_pattern, fields, pattern

    @override
    @classmethod
    def spread(cls, models: Iterable[Product]) -> "Inventory[Product]":
        inventory: dict[Path, list[Product]] = {}
        settings = Settings.get_settings()
        data_path = settings.get("data", "path")
        path_format, _, parts, _ = cls.get_parts(settings)
        for model in models:
            fields = {
                str(part): cast(str | None, getattr(model, part))
                for part in parts
            }
            path = data_path / Path(path_format.format(**fields))
            inventory.setdefault(path.resolve(), []).append(model)

        return cls(inventory, parts=parts)

    @override
    @classmethod
    def select(
        cls, session: Session, selectors: Selectors | None = None
    ) -> "Inventory[Product]":
        inventory: dict[Path, list[Product]] = {}
        settings = Settings.get_settings()
        data_path = settings.get("data", "path")
        path_format, _, parts, _ = cls.get_parts(settings)
        if not parts:
            selectors = [{}]
        elif not selectors:
            query = select(
                *(
                    cast(MappedColumn[str | None], getattr(Product, field))
                    for field in parts
                )
            ).distinct()
            selectors = [
                dict(zip(parts, values, strict=True))
                for values in session.execute(query)
            ]
            LOGGER.debug("Products files fields: %r", selectors)

        for fields in selectors:
            products = session.scalars(
                select(Product)
                .filter(Product.generic_id.is_(None))
                .filter_by(**fields)
            ).all()
            path = data_path / Path(path_format.format(**fields))
            inventory[path.resolve()] = list(products)

        return cls(inventory, parts=parts)

    @override
    @classmethod
    def read(cls, selectors: Selectors | None = None) -> "Inventory[Product]":
        inventory: dict[Path, list[Product]] = {}
        settings = Settings.get_settings()
        data_path = Path(settings.get("data", "path"))
        _, glob_pattern, parts, pattern = cls.get_parts(settings)
        for path in sorted(data_path.glob(glob_pattern)):
            if cls.filter_path(path, pattern, selectors):
                LOGGER.info("Looking at products in %s", path)
                try:
                    products = list(ProductsReader(path).read())
                    inventory[path.resolve()] = products
                except (TypeError, ValueError):
                    LOGGER.exception("Could not parse product from %s", path)

        return cls(inventory, parts=parts)

    @staticmethod
    def filter_path(
        path: Path, pattern: re.Pattern[str], selectors: Selectors | None = None
    ) -> bool:
        """
        Test whether a path to a products metadata filename matches the provided
        selectors and pattern.
        """

        if selectors is None:
            return True
        if (parts := pattern.match(str(path))) is None:
            return False

        for fields in selectors:
            if all(
                fields.get(part, value) == value
                for part, value in parts.groupdict().items()
            ):
                return True

        return False

    @override
    def get_writers(self) -> Iterator[ProductsWriter]:
        for path, products in self.items():
            yield ProductsWriter(path, products, shared_fields=self._parts)

    def _find_match(
        self, product: Product, update: bool = True, only_new: bool = False
    ) -> tuple[Product | None, bool]:
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

    @override
    def merge_update(
        self,
        other: "Inventory[Product]",
        update: bool = True,
        only_new: bool = False,
    ) -> "Inventory[Product]":
        updated: dict[Path, list[Product]] = {}
        self._matcher.fill_map(self)
        if only_new:
            update = False
        for path, products in other.items():
            changed = False
            updates: list[Product] = []
            for product in products:
                match, change = self._find_match(
                    product, update=update, only_new=only_new
                )
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

    @override
    def find(self, key: Hashable, update_map: bool = False) -> Product:
        if update_map:
            self._matcher.fill_map(self)

        return self._matcher.find_map(key)

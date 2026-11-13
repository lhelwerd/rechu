"""
Products inventory.
"""

import glob
import logging
import re
from collections.abc import Hashable, Iterable, Iterator, Sequence
from dataclasses import dataclass, field
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
from .base import Inventory, MatchMeta, Selectors

if TYPE_CHECKING:
    from _typeshed import SupportsKeysAndGetItem
else:
    SupportsKeysAndGetItem = dict

LOGGER = logging.getLogger(__name__)


@dataclass
class Parts:
    """
    Formatting, selection and matcher parts for product inventory filenames.
    """

    path_format: str
    glob_pattern: str
    fields: SharedFields
    pattern: re.Pattern[str] = field(default=re.compile(""))


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
        parts: Parts | SharedFields | None = None,
    ) -> None:
        super().__init__()
        if mapping is not None:
            self.update(mapping)
        match parts:
            case Parts():
                self._parts = set(parts.fields)
            case None:
                settings = Settings.get_settings()
                self._parts = set(self.get_parts(settings).fields)
            case _:
                self._parts = set(parts)
        self._matcher = ProductMatcher()

    @staticmethod
    def get_parts(
        settings: Settings,
    ) -> Parts:
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
        path = "".join(
            rf"{re.escape(prefix)}(?P<{key}>.*)??"
            if key is not None
            else re.escape(prefix)
            for prefix, key in zip(prefixes, keys, strict=True)
        )
        return Parts(
            path_format=path_format,
            glob_pattern="*".join(glob.escape(prefix) for prefix in prefixes),
            fields=cast(
                SharedFields, tuple(key for key in keys if key in SHARED_FIELDS)
            ),
            pattern=re.compile(rf"(^|.*/){path}$"),
        )

    @override
    @classmethod
    def spread(cls, models: Iterable[Product]) -> "Inventory[Product]":
        inventory: dict[Path, list[Product]] = {}
        settings = Settings.get_settings()
        data_path = settings.get("data", "path")
        parts = cls.get_parts(settings)
        for model in models:
            fields = {
                str(part): cast(str | None, getattr(model, part))
                for part in parts.fields
            }
            path = data_path / Path(parts.path_format.format(**fields))
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
        parts = cls.get_parts(settings)
        if not parts.fields:
            selectors = [{}]
        elif not selectors:
            selectors = [
                dict(zip(parts.fields, values, strict=True))
                for values in session.execute(
                    select(
                        *(
                            cast(
                                MappedColumn[str | None],
                                getattr(Product, field),
                            )
                            for field in parts.fields
                        )
                    ).distinct()
                )
            ]
            LOGGER.debug("Products files fields: %r", selectors)

        for fields in selectors:
            products = session.scalars(
                select(Product)
                .filter(Product.generic_id.is_(None))
                .filter_by(**fields)
            ).all()
            path = data_path / Path(parts.path_format.format(**fields))
            inventory[path.resolve()] = list(products)

        return cls(inventory, parts=parts)

    @override
    @classmethod
    def read(cls, selectors: Selectors | None = None) -> "Inventory[Product]":
        inventory: dict[Path, list[Product]] = {}
        settings = Settings.get_settings()
        data_path = Path(settings.get("data", "path"))
        parts = cls.get_parts(settings)
        for path in sorted(data_path.glob(parts.glob_pattern)):
            if cls.filter_path(path, parts.pattern, selectors):
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
        self,
        product: Product,
        update: bool = True,
        only_new: bool = False,
        previous: Sequence[Product] = (),
    ) -> MatchMeta[Product]:
        changed = False
        existing = self._matcher.check_map(product)
        if existing is None:
            changed = True
            existing = product
            index = len(previous)
        elif only_new:
            return MatchMeta()
        else:
            index = previous.index(existing)
            if not update:
                existing = existing.copy()

        if existing.merge(product):
            changed = True
        return MatchMeta(match=existing, index=index, changed=changed)

    @override
    def merge_update(
        self,
        other: "Inventory[Product]",
        complete: bool = True,
        update: bool = True,
        only_new: bool = False,
    ) -> "Inventory[Product]":
        updated: dict[Path, list[Product]] = {}
        self._matcher.fill_map(self)
        if only_new:
            complete = False
            update = False
        for path, products in other.items():
            changed = False
            updates: list[Product] = []
            previous = list(self.get(path, []))
            for product in products:
                result = self._find_match(
                    product,
                    update=update,
                    only_new=only_new,
                    previous=previous,
                )
                changed = changed or result.changed
                if result.changed and result.match is not None:
                    updates.append(result.match)
                    previous[result.index : (result.index + 1)] = [result.match]

            if update:
                self[path] = previous
            if complete:
                updates = previous.copy()
            if changed:
                updated[path] = updates

        return Products(updated, parts=self._parts)

    @override
    def find(self, key: Hashable, update_map: bool = False) -> Product:
        if update_map:
            self._matcher.fill_map(self)

        return self._matcher.find_map(key)

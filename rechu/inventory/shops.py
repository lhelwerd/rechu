"""
Shops inventory.
"""

from collections.abc import Hashable, Iterable, Iterator
import logging
from pathlib import Path
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from .base import Inventory, Selectors
from ..io.shops import ShopsReader, ShopsWriter
from ..models.shop import Shop
from ..settings import Settings

LOGGER = logging.getLogger(__name__)

class Shops(dict, Inventory[Shop]):
    """
    Inventory of shops.
    """

    def __init__(self, mapping = None, /):
        super().__init__()
        if mapping is not None:
            self.update(mapping)
        self._update_map()

    def _update_map(self) -> None:
        self._map: dict[Hashable, Shop] = {
            shop.key: shop for shop in self.get(self._get_path(), [])
        }

    @staticmethod
    def _get_path() -> Path:
        settings = Settings.get_settings()
        data_path = settings.get('data', 'path')
        shops_path = data_path / Path(settings.get('data', 'shops'))
        return shops_path.resolve()

    @classmethod
    def spread(cls, models: Iterable[Shop]) -> "Inventory[Shop]":
        return cls({cls._get_path(): models})

    @classmethod
    def select(cls, session: Session,
               selectors: Optional[Selectors] = None) -> "Inventory[Shop]":
        if selectors:
            raise ValueError("Shop inventory does not support selectors")

        shops = session.scalars(select(Shop)).all()
        return cls({cls._get_path(): shops})

    @classmethod
    def read(cls) -> "Inventory[Shop]":
        path = cls._get_path()
        try:
            shops = list(ShopsReader(path).read())
        except (TypeError, ValueError):
            LOGGER.exception('Could not parse shop from %s', path)
            shops = []

        return cls({path: shops})

    def get_writers(self) -> Iterator[ShopsWriter]:
        path = self._get_path()
        if path in self:
            yield ShopsWriter(path, self[path])

    def merge_update(self, other: "Inventory[Shop]", update: bool = True,
                     only_new: bool = False) -> "Inventory[Shop]":
        updates: list[Shop] = []
        path = self._get_path()
        if only_new:
            update = False

        self._update_map()
        changed = False
        for shop in other.get(path, []):
            existing = self._map.get(shop.key)
            if existing is None:
                changed = True
                existing = shop
            elif only_new:
                continue
            if not update:
                existing = existing.copy()
            if existing.merge(shop):
                changed = True

            updates.append(existing)

        if update:
            previous = list(self.get(path, []))
            self[path] = previous + [
                change for change in updates if change not in previous
            ]
            updates = self[path].copy()

        if not changed:
            return Shops()

        return Shops({path: updates})

    def find(self, key: Hashable, update_map: bool = False) -> Shop:
        if update_map:
            self._update_map()

        if (shop := self._map.get(key)) is not None:
            return shop
        if isinstance(key, str):
            return Shop(key=key)

        raise TypeError("Cannot construct empty Shop metadata from key of type "
                        f"{type(key)!r}: {key!r}")

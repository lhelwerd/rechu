"""
Shops inventory.
"""

from collections.abc import Iterable, Iterator
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
        self._map = {shop.key: shop for shop in self.get(self._get_path(), [])}

    @staticmethod
    def _get_path() -> Path:
        settings = Settings.get_settings()
        data_path = settings.get('data', 'path')
        return data_path / Path(settings.get('data', 'shops'))

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
    def read(cls) -> "Inventory[Product]":
        path = cls._get_path()
        try:
            shops = list(ShopsReader(path).read())
        except (TypeError, ValueError):
            LOGGER.exception('Could not parse product from %s', path)
            shops = []

        return cls({path: shops})

    def get_writers(self) -> Iterator[ShopsWriter]:
        path = self._get_path()
        yield ShopsWriter(path, self.get(path, []))

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
                # TODO: Merge

            updates.append(existing)

        if update:
            self.setdefault(path, [])
            self[path].extend(change for change in updates
                              if change not in self[path])
            self._update_map()
            updates = self[path].copy()

        if not changed:
            return Shops()

        return Shops({path: updates})

    def find(self, key: str, update_map: bool = False) -> Shop:
        """
        Find metadata for a shop identified by its `key`, or create empty Shop
        metadata with only the key defined if the shop is not in the inventory.
        If `update_map` is True, ensures that the most recent changes to the
        inventory are reflected, otherwise direct mutations of path elements
        may not be considered.
        """

        if update_map:
            self._update_map()
        if (shop := self._map.get(key)) is None:
            shop = Shop(key=key)
        return shop

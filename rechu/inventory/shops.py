"""
Shops inventory.
"""

import logging
from collections.abc import Hashable, Iterable, Iterator
from pathlib import Path
from typing import TYPE_CHECKING, final

from sqlalchemy import select
from sqlalchemy.orm import Session
from typing_extensions import override

from ..io.shops import ShopsReader, ShopsWriter
from ..models.shop import Shop
from ..settings import Settings
from .base import Inventory, Selectors

if TYPE_CHECKING:
    from _typeshed import SupportsKeysAndGetItem
else:
    SupportsKeysAndGetItem = dict

LOGGER = logging.getLogger(__name__)


@final
class Shops(Inventory[Shop], dict[Path, list[Shop]]):
    """
    Inventory of shops.
    """

    __getitem__ = dict[Path, list[Shop]].__getitem__
    __iter__ = dict[Path, list[Shop]].__iter__
    __len__ = dict[Path, list[Shop]].__len__
    __hash__ = dict[Path, list[Shop]].__hash__

    def __init__(
        self,
        mapping: SupportsKeysAndGetItem[Path, list[Shop]] | None = None,
        /,
    ) -> None:
        super().__init__()
        if mapping is not None:
            self.update(mapping)
        self._update_map()

    def _update_map(self) -> None:
        self._map: dict[Hashable, tuple[int, Shop]] = {
            shop.key: (index, shop)
            for index, shop in enumerate(self.get(self._get_path(), []))
        }

    @staticmethod
    def _get_path() -> Path:
        settings = Settings.get_settings()
        data_path = settings.get("data", "path")
        shops_path = data_path / Path(settings.get("data", "shops"))
        return shops_path.resolve()

    @override
    @classmethod
    def spread(cls, models: Iterable[Shop]) -> "Inventory[Shop]":
        return cls({cls._get_path(): list(models)})

    @override
    @classmethod
    def select(
        cls, session: Session, selectors: Selectors | None = None
    ) -> "Inventory[Shop]":
        if selectors:
            raise ValueError("Shop inventory does not support selectors")

        shops = list(session.scalars(select(Shop)).all())
        return cls({cls._get_path(): shops})

    @override
    @classmethod
    def read(cls, selectors: Selectors | None = None) -> "Inventory[Shop]":
        if selectors:
            raise ValueError("Shop inventory does not support selectors")

        path = cls._get_path()
        try:
            shops = list(ShopsReader(path).read())
        except (TypeError, ValueError, FileNotFoundError):
            LOGGER.exception("Could not parse shop from %s", path)
            shops = []

        return cls({path: shops})

    @override
    def get_writers(self) -> Iterator[ShopsWriter]:
        path = self._get_path()
        if path in self:
            yield ShopsWriter(path, self[path])

    def _find_match(
        self,
        shop: Shop,
        update: bool = True,
        only_new: bool = False,
        count: int = 0,
    ) -> tuple[Shop | None, int, bool]:
        changed = False
        pair = self._map.get(shop.key)
        if pair is None:
            changed = True
            existing = shop
            index = count
        elif only_new:
            return None, -1, False
        else:
            index, existing = pair
            if not update:
                existing = existing.copy()
        if existing.merge(shop):
            changed = True
        return existing, index, changed

    @override
    def merge_update(
        self,
        other: "Inventory[Shop]",
        complete: bool = True,
        update: bool = True,
        only_new: bool = False,
    ) -> "Inventory[Shop]":
        updates: list[Shop] = []
        path = self._get_path()
        if only_new:
            complete = False
            update = False

        self._update_map()
        changed = False
        previous = list(self.get(path, []))
        for shop in other.get(path, []):
            match, index, change = self._find_match(
                shop, update=update, only_new=only_new, count=len(previous)
            )
            changed = changed or change
            if change and match is not None:
                updates.append(match)
                previous[index : (index + 1)] = [match]

        if update:
            self[path] = previous
        if complete:
            updates = previous.copy()

        if not changed:
            return Shops()

        return Shops({path: updates})

    @override
    def find(self, key: Hashable, update_map: bool = False) -> Shop:
        if update_map:
            self._update_map()

        if (pair := self._map.get(key)) is not None:
            _, shop = pair
            return shop
        if isinstance(key, str):
            return Shop(key=key)

        raise TypeError(
            "Cannot construct empty Shop metadata from key of "
            + f"type {type(key)!r}: {key!r}"
        )

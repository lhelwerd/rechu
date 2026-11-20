"""
Database entity matching methods.
"""

import logging
from abc import ABCMeta, abstractmethod
from collections.abc import Collection, Hashable, Iterable, Iterator, Sequence
from enum import Enum, auto
from typing import Generic, TypeVar

from sqlalchemy.orm import Session

from ..inventory.base import Inventory
from ..models.base import Base as ModelBase, Origin

IT = TypeVar("IT", bound=ModelBase)
CT = TypeVar("CT", bound=ModelBase)

LOGGER = logging.getLogger(__name__)


class OnDuplicate(Enum):
    """
    Parameter to determine what to do if the matcher already contains a candiate
    in the same key.
    """

    IGNORE = auto()
    REPLACE = auto()
    DROP = auto()
    ADD = auto()


class ConstructError(TypeError):
    """
    Exception indicating that a candidate was not found in the map and could not
    be constructed from the key either.
    """


class Matcher(Generic[IT, CT], metaclass=ABCMeta):
    """
    Generic item candidate model matcher.
    """

    def __init__(self) -> None:
        self._map: dict[Hashable, dict[CT, int]] | None = None

    @abstractmethod
    def find_candidates(
        self,
        session: Session,
        items: Collection[IT] = (),
        extra: Collection[CT] = (),
        only_unmatched: bool = False,
    ) -> Iterator[tuple[CT, IT]]:
        """
        Detect candidate models in the database that match items. Optionally,
        the `items` may be provided, which might not have been inserted or
        updated in the database, otherwise all items from the database are
        attempted for matching. Moreover, `extra` candidates may be provided,
        which in their case augment those from the database. If `only_unmatched`
        is enabled, then only items that do not have a relation with a candidate
        model are attempted for matching. The resulting iterator provides tuples
        of matches between candidates and items which have not had an update to
        their match relationship yet; multiple candidate models may be indicated
        for a single item model.
        """

        raise NotImplementedError("Search must be implemented by subclasses")

    def filter_duplicate_candidates(
        self,
        candidates: Iterable[tuple[CT, IT]],
        preferred: Collection[CT] = (),
        preferred_origin: Origin = Origin.DATABASE,
    ) -> Iterator[tuple[CT, IT]]:
        """
        Detect if item models were matched against multiple candidates and
        filter out such models. If preferred candidate models are provided, then
        any match with such candidates may only be filtered out if other matches
        are also with preferred candidate models.
        """

        seen: dict[IT, CT | None] = {}
        preferred_candidates = frozenset(preferred)
        for candidate, item in candidates:
            previous = seen.get(item, False)
            previous_preferred = previous in preferred_candidates
            new_preferred = candidate in preferred_candidates
            if previous is not False and previous_preferred == new_preferred:
                seen[item] = self.select_duplicate(
                    candidate, seen[item], preferred_origin
                )
            elif not previous_preferred:
                seen[item] = candidate
        for item, unique in seen.items():
            if unique is not None:
                yield unique, item

    def select_duplicate(
        self,
        candidate: CT,
        duplicate: CT | None,
        preferred_origin: Origin = Origin.DATABASE,
    ) -> CT | None:
        """
        Determine which of two candidate models should be matched against some
        item, if any. If this returns `None` than neither of the models is
        provided as a match.
        """

        _ = preferred_origin
        if candidate is duplicate:
            return candidate

        return None

    @abstractmethod
    def match(self, candidate: CT, item: IT) -> bool:
        """
        Check if a candidate model matches an item model without looking up
        through the database.
        """

        raise NotImplementedError("Match must be implemented by subclasses")

    @abstractmethod
    def get_keys(self, product: CT) -> Iterator[Hashable]:
        """
        Generate a number of identifying keys for candidate models.
        """

        raise NotImplementedError("Key must be implemented by subclasses")

    @abstractmethod
    def select_candidates(
        self, session: Session, exclude: Collection[CT] = ()
    ) -> Sequence[CT]:
        """
        Retrieve candidate models from the database.

        Models in the `exclude` collection are not collected from the database.
        """

        raise NotImplementedError("Select must be implemented by subclasses")

    def load_map(
        self, session: Session, on_duplicate: OnDuplicate = OnDuplicate.IGNORE
    ) -> None:
        """
        Create a mapping of unique keys of candidate models to their database
        entities.
        """

        self._map = {}
        for candidate in self.select_candidates(session):
            _ = self.add_map(candidate, on_duplicate)

    def clear_map(self) -> None:
        """
        Clear the mapping of unique keys of candidate models to entities
        such that it no database entities are matched.
        """

        self._map = {}

    def fill_map(
        self,
        inventory: Inventory[CT],
        on_duplicate: OnDuplicate = OnDuplicate.IGNORE,
    ) -> None:
        """
        Update a mapping of unique keys of candidate models from a filled
        inventory.
        """

        if self._map is None or on_duplicate == OnDuplicate.DROP:
            self._map = {}
        for group in inventory.values():
            for model in group:
                _ = self.add_map(model, on_duplicate)

    def add_map(
        self, candidate: CT, on_duplicate: OnDuplicate = OnDuplicate.IGNORE
    ) -> bool:
        """
        Manually add a candidate model to a mapping of unique keys. Returns
        whether the entity was actually added. If the map is not initialized,
        the candidate is never added. If a key is not unique enough and
        `replace` is disabled, then that key is not given the new candidate.
        """

        if self._map is None:
            return False

        add = False
        for key in self.get_keys(candidate):
            match (on_duplicate, bool(self._map.get(key))):
                case OnDuplicate.REPLACE, True:
                    add = candidate not in self._map[key]
                    self._map[key] = {candidate: 0}
                case OnDuplicate.DROP, True:
                    if tuple(self._map[key].keys()) != (candidate,):
                        del self._map[key]
                case OnDuplicate.IGNORE, True:
                    continue
                case OnDuplicate.ADD, True:
                    if candidate not in self._map[key]:
                        self._map[key][candidate] = len(self._map[key])
                        add = True
                case _:  # Any on_duplicate with no existing map entry
                    add = True
                    self._map[key] = {candidate: 0}

        return add

    def discard_map(self, candidate: CT) -> bool:
        """
        Remove a candidate model to a mapping of unique keys. Returns whether
        the entity was actually removed.
        """

        if self._map is None:
            return False

        remove = False
        for key in self.get_keys(candidate):
            try:
                found = self._map[key]
                try:
                    del found[candidate]
                    remove = True
                except KeyError:
                    LOGGER.warning(
                        "Candidate instance %r is not stored at %r: %r",
                        candidate,
                        key,
                        found,
                    )
            except KeyError:
                pass

        return remove

    def check_map(self, candidate: CT) -> tuple[CT | None, Collection[CT]]:
        """
        Retrieve a candidate model obtained from the database which has one or
        more of the unique keys in common with the provided `candidate` plus all
        models that also have this common key. If no such candidate is found,
        then `None` and an empty set is returned. Any returned models should be
        considered read-only and may be from earlier database sessions.
        """

        if self._map is None:
            return None, frozenset()

        for key in self.get_keys(candidate):
            try:
                return next(iter(self._map[key])), self._map[key].keys()
            except (KeyError, StopIteration):
                pass

        return None, frozenset()

    def find_map(self, key: Hashable) -> CT:
        """
        Find a candidate in the filled map based on one of its identifying hash
        keys, or create an empty candidate model  with only properties deduced
        from the hash key. Raises a `TypeError` if the hash is not useful for
        deducing a model or its properties.
        """

        if self._map is not None:
            try:
                return next(iter(self._map[key]))
            except (KeyError, StopIteration):
                pass

        raise ConstructError(
            "Cannot lookup in map or construct external candidate"
        )

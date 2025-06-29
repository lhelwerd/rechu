"""
Database entity matching methods.
"""

from collections.abc import Collection, Hashable, Iterable, Iterator
from typing import Generic, Optional, TypeVar
from sqlalchemy.orm import Session
from ..inventory.base import Inventory
from ..models.base import Base as ModelBase

IT = TypeVar('IT', bound=ModelBase)
CT = TypeVar('CT', bound=ModelBase)

class Matcher(Generic[IT, CT]):
    """
    Generic item candidate model matcher.
    """

    def __init__(self) -> None:
        self._map: Optional[dict[Hashable, CT]] = None

    def find_candidates(self, session: Session,
                        items: Collection[IT] = (),
                        extra: Collection[CT] = (),
                        only_unmatched: bool = False) \
            -> Iterator[tuple[CT, IT]]:
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

        raise NotImplementedError('Search must be implemented by subclasses')

    def filter_duplicate_candidates(self, candidates: Iterable[tuple[CT, IT]]) \
            -> Iterator[tuple[CT, IT]]:
        """
        Detect if item models were matched against multiple candidates and
        filter out such models.
        """

        seen: dict[IT, Optional[CT]] = {}
        for candidate, item in candidates:
            if item in seen:
                seen[item] = self.select_duplicate(candidate, seen[item])
            else:
                seen[item] = candidate
        for item, unique in seen.items():
            if unique is not None:
                yield unique, item

    def select_duplicate(self, candidate: CT, duplicate: Optional[CT]) \
            -> Optional[CT]: # pylint: disable=unused-argument
        """
        Determine which of two candidate models should be matched against some
        item, if any. If this returns `None` than neither of the models is
        provided as a match.
        """

        if candidate is duplicate:
            return candidate

        return None

    def match(self, candidate: CT, item: IT) -> bool:
        """
        Check if a candidate model matches an item model without looking up
        through the database.
        """

        raise NotImplementedError('Match must be implemented by subclasses')

    def load_map(self, session: Session) -> None:
        """
        Create a mapping of unique keys of candidate models to their database
        entities.
        """
        # pylint: disable=unused-argument

        self._map = {}

    def clear_map(self) -> None:
        """
        Clear the mapping of unique keys of candidate models to entities
        such that it no database entities are matched.
        """

        self._map = {}

    def fill_map(self, inventory: Inventory[CT]) -> None:
        """
        Update a mapping of unique keys of candidate models from a filled
        inventory.
        """

        if self._map is None:
            self._map = {}
        for group in inventory.values():
            for model in group:
                self.add_map(model)

    def add_map(self, candidate: CT) -> bool:
        """
        Manually add a candidate model to a mapping of unique keys. Returns
        whether the entity was actually added, which is not done if the map is
        not initialized or the keys are not unique enough.
        """
        # pylint: disable=unused-argument

        return False

    def discard_map(self, candidate: CT) -> bool:
        """
        Remove a candidate model to a mapping of unique keys. Returns whether
        the entity was actually removed.
        """
        # pylint: disable=unused-argument

        return False

    def check_map(self, candidate: CT) -> Optional[CT]:
        """
        Retrieve a candidate model obtained from the database which has one or
        more of the unique keys in common with the provided `candidate`. If no
        such candidate is found, then `None` is returned. Any returned candidate
        should be considered read-only due to it coming from an earlier session
        that is already closed.
        """
        # pylint: disable=unused-argument

        return None

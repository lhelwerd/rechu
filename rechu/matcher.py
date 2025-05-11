"""
Database entity matching methods.
"""

from collections.abc import Hashable, Iterable, Iterator, Sequence
from datetime import date
import logging
from typing import Generic, Optional, TypeVar
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import aliased, Session
from sqlalchemy.sql.functions import coalesce
from .models.base import Base as ModelBase, Price
from .models.product import Product, LabelMatch, PriceMatch, DiscountMatch
from .models.receipt import Receipt, ProductItem, Discount, DiscountItems

IT = TypeVar('IT', bound=ModelBase)
CT = TypeVar('CT', bound=ModelBase)

class Matcher(Generic[IT, CT]):
    """
    Generic item candidate model matcher.
    """

    def __init__(self) -> None:
        self._map: Optional[dict[Hashable, CT]] = None

    def find_candidates(self, session: Session,
                        items: Optional[Sequence[IT]] = None,
                        only_unmatched: bool = False) \
            -> Iterator[tuple[CT, IT]]:
        """
        Detect candidate models in the database that match the provided items.
        Optionally, the `items` may be provided (which might not be inserted or
        updated in the database). If `only_unmatched` is enabled, then only
        items that do not have a relation with a candidate model are provided.
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
                seen[item] = None
            else:
                seen[item] = candidate
        for item, unique in seen.items():
            if unique is not None:
                yield unique, item

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

    def add_map(self, candidate: CT) -> bool:
        """
        Manually add a candidate model to a mapping of unique keys. Returns
        whether the entity was actually added, which is not done if the map is
        not initialized or the keys are not unique enough.
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

class ProductMatcher(Matcher[ProductItem, Product]):
    """
    Matcher for receipt product items and product metadata.
    """

    IND_MINIMUM = 'minimum'
    IND_MAXIMUM = 'maximum'

    MAP_MATCH = 'match'
    MAP_SKU = 'sku'
    MAP_GTIN = 'gtin'

    def _find_dirty_candidates(self, session: Session,
                               items: Sequence[ProductItem],
                               only_unmatched: bool = False) \
            -> Iterator[tuple[Product, ProductItem]]:
        products = session.scalars(select(Product).order_by(Product.id)) \
            .all()
        for item in items:
            if only_unmatched and item.product_id is not None:
                continue
            for product in products:
                if self.match(product, item):
                    yield product, item

    def find_candidates(self, session: Session,
                        items: Optional[Sequence[ProductItem]] = None,
                        only_unmatched: bool = False) \
            -> Iterator[tuple[Product, ProductItem]]:
        if items is not None and \
            any(item.id is None or item in session.dirty for item in items):
            yield from self._find_dirty_candidates(session, items,
                                                   only_unmatched)
            return

        minimum = aliased(PriceMatch)
        maximum = aliased(PriceMatch)
        other = aliased(PriceMatch)
        item_join = and_(ProductItem.label == coalesce(LabelMatch.name,
                                                       ProductItem.label),
                         ProductItem.price == coalesce(other.value,
                                                       ProductItem.price),
                         ProductItem.price.between(coalesce(minimum.value,
                                                            ProductItem.price),
                                                   coalesce(maximum.value,
                                                            ProductItem.price)))
        discount_join = and_(Discount.id == DiscountItems.c.discount_id,
                             or_(DiscountMatch.label.is_(None),
                                 DiscountMatch.label == Discount.label))
        query = select(Product, ProductItem) \
            .join(LabelMatch, isouter=True) \
            .join(other, Product.prices.and_(coalesce(other.indicator, '')
                                             .notin_((self.IND_MINIMUM,
                                                      self.IND_MAXIMUM))),
                  isouter=True) \
            .join(minimum,
                  Product.prices.and_(minimum.indicator == self.IND_MINIMUM),
                  isouter=True) \
            .join(maximum,
                  Product.prices.and_(maximum.indicator == self.IND_MAXIMUM),
                  isouter=True) \
            .join(DiscountMatch, isouter=True) \
            .join(ProductItem, item_join) \
            .join(Receipt,
                  ProductItem.receipt.and_(Receipt.shop == Product.shop)) \
            .join(DiscountItems,
                  ProductItem.id == DiscountItems.c.product_id,
                  isouter=True) \
            .join(Discount, discount_join, isouter=True) \
            .order_by(ProductItem.id, Product.id)
        if items is not None:
            query = query \
                .filter(ProductItem.id.in_((item.id for item in items)))
        if only_unmatched:
            query = query.filter(ProductItem.product_id.is_(None))
        logging.warning('%s', query)
        for row in session.execute(query):
            if self.match(row.Product, row.ProductItem):
                yield row.Product, row.ProductItem

    @classmethod
    def _match_price(cls, price: PriceMatch, item_value: Price,
                     item_date: date) -> int:
        if (price.indicator == cls.IND_MINIMUM and price.value <= item_value) \
            or \
           (price.indicator == cls.IND_MAXIMUM and price.value >= item_value):
            return 1
        if (price.indicator is None or
            price.indicator == str(item_date.year)) and \
            price.value == item_value:
            return 2

        return 0

    def match(self, candidate: Product, item: ProductItem) -> bool:
        if candidate.shop != item.receipt.shop or (
                not candidate.labels and not candidate.prices and
                not candidate.discounts
            ):
            return False
        if candidate.labels and \
            all(label.name != item.label for label in candidate.labels):
            return False

        seen_price = 0
        item_price = Price(item.price)
        for price in candidate.prices:
            seen_price += self._match_price(price, item_price,
                                            item.receipt.date)
        # Must adhere to both 'minimum' and 'maximum', one date indicator or
        # no indicator
        if candidate.prices and seen_price < 2:
            return False

        for discount in candidate.discounts:
            if all(discount.label != bonus.label for bonus in item.discounts):
                return False

        return True

    @staticmethod
    def _get_product_match(product: Product) -> Hashable:
        return (
            product.shop,
            tuple(label.name for label in product.labels),
            tuple(
                (price.indicator, price.value)
                for price in product.prices
            ),
            tuple(discount.label for discount in product.discounts)
        )

    def load_map(self, session: Session) -> None:
        self._map = {}
        for product in session.scalars(select(Product)):
            self.add_map(product)

    def add_map(self, candidate: Product) -> bool:
        if self._map is None:
            return False

        keys = (
            (self.MAP_MATCH, self._get_product_match(candidate)),
            (self.MAP_SKU, candidate.shop, candidate.sku),
            (self.MAP_GTIN, candidate.gtin)
        )
        add = False
        for key in keys:
            if key[-1] is not None:
                add = self._map.setdefault(key, candidate) is candidate or add

        return add

    def check_map(self, candidate: Product) -> Optional[Product]:
        if self._map is None:
            return None
        match = self._get_product_match(candidate)
        if (self.MAP_MATCH, match) in self._map:
            return self._map[(self.MAP_MATCH, match)]
        if (self.MAP_SKU, candidate.shop, candidate.sku) in self._map:
            return self._map[(self.MAP_SKU, candidate.shop, candidate.sku)]
        if (self.MAP_GTIN, candidate.gtin) in self._map:
            return self._map[(self.MAP_GTIN, candidate.gtin)]
        return None

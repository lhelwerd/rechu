"""
Product metadata matcher.
"""

from collections.abc import Collection, Hashable, Iterator, Set
from enum import Enum
import logging
from typing import Optional
from sqlalchemy import and_, or_, cast, literal, select, Select, String
from sqlalchemy.orm import aliased, Session
from sqlalchemy.sql.expression import extract
from sqlalchemy.sql.functions import coalesce
from .base import Matcher
from ..models.base import Price, Quantity
from ..models.product import Product, LabelMatch, PriceMatch, DiscountMatch
from ..models.receipt import Receipt, ProductItem, Discount, DiscountItems

LOGGER = logging.getLogger(__name__)

class MapKey(Enum):
    """
    Keys for a map of products with unique matchers and identifiers.
    """

    MAP_MATCH = 'match'
    MAP_SKU = 'sku'
    MAP_GTIN = 'gtin'

_MAP_KEYS = frozenset({MapKey.MAP_MATCH, MapKey.MAP_SKU, MapKey.MAP_GTIN})

class ProductMatcher(Matcher[ProductItem, Product]):
    """
    Matcher for receipt product items and product metadata.
    """

    IND_MINIMUM = 'minimum'
    IND_MAXIMUM = 'maximum'

    def __init__(self, map_keys: Set[MapKey] = _MAP_KEYS) -> None:
        super().__init__()
        self.discounts = True
        self._map_keys = map_keys

    def _get_specificity(self, product: Product) -> tuple[int, ...]:
        # A product has higher specificity if it has more of the three types
        # of matcher fields (label/price/discount) than another product, or if
        # they both have the same of these, then it is preferred if it has
        # fewer of the individual fields.
        matchers = bool(product.labels) + bool(product.prices)
        matcher_fields = len(product.labels) + len(product.prices)
        if self.discounts:
            matchers += bool(product.discounts)
            matcher_fields += len(product.discounts)
        return (matchers, -matcher_fields)

    def _select_generic(self, generic: Product, sub_range: Product) -> Product:
        if self._get_specificity(generic) >= self._get_specificity(sub_range):
            return generic

        return sub_range

    def select_duplicate(self, candidate: Product,
                         duplicate: Optional[Product]) -> Optional[Product]:
        if duplicate is not None:
            if candidate.id is not None and candidate.id == duplicate.id:
                return candidate
            if candidate.generic == duplicate:
                return self._select_generic(duplicate, candidate)
            if duplicate.generic == candidate:
                return self._select_generic(candidate, duplicate)
            if candidate is not duplicate and \
                candidate.generic == duplicate.generic:
                return candidate.generic
        return super().select_duplicate(candidate, duplicate)

    def _propose(self, product: Product,
                 item: ProductItem) -> Iterator[tuple[Product, ProductItem]]:
        if self.match(product, item):
            yield product, item

    def _propose_extra(self, item: ProductItem, extra: Collection[Product]) \
            -> Iterator[tuple[Product, ProductItem]]:
        for product in extra:
            yield from self._propose(product, item)
            for product_range in product.range:
                yield from self._propose(product_range, item)

    def _find_dirty_candidates(self, session: Session,
                               items: Collection[ProductItem],
                               extra: Collection[Product],
                               only_unmatched: bool = False) \
            -> Iterator[tuple[Product, ProductItem]]:
        extra_ids = {product.id for product in extra if product.id is not None}
        products = \
            session.scalars(select(Product)
                            .filter(Product.id.notin_(extra_ids))
                            .order_by(Product.generic_id.asc().nulls_first(),
                                      Product.id)).all()
        for item in items:
            if only_unmatched and item.product_id is not None:
                continue
            for product in products:
                yield from self._propose(product, item)
            yield from self._propose_extra(item, extra)

    def find_candidates(self, session: Session,
                        items: Collection[ProductItem] = (),
                        extra: Collection[Product] = (),
                        only_unmatched: bool = False) \
            -> Iterator[tuple[Product, ProductItem]]:
        if any(item.id is None or item in session.dirty for item in items):
            yield from self._find_dirty_candidates(session, items, extra,
                                                   only_unmatched)
            return

        query = self._build_query(items, extra, only_unmatched)
        LOGGER.debug('%s', query)
        seen = set()
        extra_ids = {product.id for product in extra if product.id is not None}
        for row in session.execute(query):
            if row.Product is not None and row.Product.id not in extra_ids:
                yield from self._propose(row.Product, row.ProductItem)
            if row.ProductItem not in seen:
                seen.add(row.ProductItem)
                yield from self._propose_extra(row.ProductItem, extra)

    def _build_query(self, items: Collection[ProductItem],
                     extra: Collection[Product],
                     only_unmatched: bool) -> Select:
        minimum = aliased(PriceMatch)
        maximum = aliased(PriceMatch)
        other = aliased(PriceMatch)
        item_join = and_(ProductItem.label == coalesce(LabelMatch.name,
                                                       ProductItem.label),
                         ProductItem.price == coalesce(other.value *
                                                       ProductItem.amount,
                                                       ProductItem.price),
                         ProductItem.price.between(coalesce(minimum.value *
                                                            ProductItem.amount,
                                                            ProductItem.price),
                                                   coalesce(maximum.value *
                                                            ProductItem.amount,
                                                            ProductItem.price)))
        price_join = or_(other.value.is_(None),
                         ProductItem.unit.is_not_distinct_from(other.indicator),
                         other.indicator == cast(extract("year", Receipt.date),
                                                 String))
        query = select(ProductItem, Product)
        if extra:
            query = query.select_from(ProductItem) \
                .join(Product, literal(value=True), isouter=True) \
                .filter(item_join)
        else:
            query = query.select_from(Product)
        query = query.join(LabelMatch, Product.labels, isouter=True) \
            .join(other, Product.prices.and_(coalesce(other.indicator, '')
                                             .notin_((self.IND_MINIMUM,
                                                      self.IND_MAXIMUM))),
                  isouter=True) \
            .join(minimum,
                  Product.prices.and_(minimum.indicator == self.IND_MINIMUM),
                  isouter=True) \
            .join(maximum,
                  Product.prices.and_(maximum.indicator == self.IND_MAXIMUM),
                  isouter=True)
        if not extra:
            query = query.join(ProductItem, item_join)
        query = query.join(Receipt, ProductItem.receipt
                           .and_(Receipt.shop == coalesce(Product.shop,
                                                          Receipt.shop))
                           .and_(price_join))
        if self.discounts:
            discount_join = and_(Discount.id == DiscountItems.c.discount_id,
                                 Discount.label == coalesce(DiscountMatch.label,
                                                            Discount.label))
            query = query.join(DiscountMatch, Product.discounts, isouter=True) \
                .join(DiscountItems,
                      ProductItem.id == DiscountItems.c.product_id,
                      isouter=True) \
                .join(Discount, discount_join, isouter=True)
        if items:
            query = query \
                .filter(ProductItem.id.in_((item.id for item in items)))
        if only_unmatched:
            query = query.filter(ProductItem.product_id.is_(None))
        query = query.order_by(ProductItem.id,
                               Product.generic_id.asc().nulls_first(),
                               Product.id)

        return query

    @classmethod
    def _match_price(cls, price: PriceMatch, item: ProductItem) -> int:
        if item.quantity.unit is not None:
            try:
                quantity = Quantity(price.value, unit=f"1 / {price.indicator}")
                if quantity * item.quantity == item.price:
                    return 2
            except ValueError:
                pass

            return 0

        match_price = Quantity(price.value) * item.quantity
        if (price.indicator == cls.IND_MINIMUM and match_price <= item.price) \
            or \
           (price.indicator == cls.IND_MAXIMUM and match_price >= item.price):
            return 1
        if (price.indicator is None or
            price.indicator == str(item.receipt.date.year)) and \
            match_price == item.price:
            return 2

        return 0

    def match(self, candidate: Product, item: ProductItem) -> bool:
        # Candidate must be from the same shop and have at least one matcher
        # Currently, candidate must be generic instead of from a product range
        if candidate.shop != item.receipt.shop or (
                not candidate.labels and not candidate.prices and
                not candidate.discounts
            ):
            return False

        # One label matcher (if existing) must be the same as item label.
        if candidate.labels and \
            all(label.name != item.label for label in candidate.labels):
            return False

        seen_price = 0
        for price in candidate.prices:
            seen_price += self._match_price(price, item)
        # Must adhere to both 'minimum' and 'maximum', one date indicator,
        # one unit indicator or one price with no indicator. No price matchers
        # is also acceptable.
        if candidate.prices and seen_price < 2:
            return False

        # Final match check with discounts, one matching discount is enough.
        # No discount matcher is accepted, and so is an item without discounts
        # when the discount matching mode is disabled.
        if not candidate.discounts or not (self.discounts or item.discounts):
            return True
        for discount in candidate.discounts:
            if any(discount.label == bonus.label for bonus in item.discounts):
                return True

        return False

    @staticmethod
    def _get_product_match(product: Product) -> Optional[Hashable]:
        if not product.labels and not product.prices and not product.discounts:
            return None
        return (
            product.shop,
            tuple(label.name for label in product.labels),
            tuple(
                (price.indicator, price.value)
                for price in product.prices
            ),
            tuple(discount.label for discount in product.discounts)
        )

    def _get_keys(self, product: Product) -> tuple[tuple[Hashable, ...], ...]:
        keys = (
            (MapKey.MAP_MATCH, self._get_product_match(product)),
            (MapKey.MAP_SKU, product.shop, product.sku),
            (MapKey.MAP_GTIN, product.shop, product.gtin)
        )
        return tuple(key for key in keys if key[0] in self._map_keys)

    def load_map(self, session: Session) -> None:
        self._map = {}
        query = select(Product).order_by(Product.generic_id.asc().nulls_first(),
                                         Product.id)
        for product in session.scalars(query):
            self.add_map(product)

    def add_map(self, candidate: Product) -> bool:
        if self._map is None:
            return False

        add = False
        for key in self._get_keys(candidate):
            if key[-1] is not None:
                add = self._map.setdefault(key, candidate) is candidate or add

        for product_range in candidate.range:
            add = self.add_map(product_range) or add

        return add

    def discard_map(self, candidate: Product) -> bool:
        if self._map is None:
            return False

        remove = False
        for key in self._get_keys(candidate):
            product = self._map.pop(key, None)
            if product is candidate:
                remove = True
            elif product is not None:
                LOGGER.warning('Product instance stored at %r is not %r: %r',
                               key, candidate, product)
                self._map[key] = product

        for product_range in candidate.range:
            remove = self.discard_map(product_range) or remove

        return remove

    def check_map(self, candidate: Product) -> Optional[Product]:
        if self._map is None:
            return None
        for key in self._get_keys(candidate):
            if key in self._map:
                return self._map[key]

        return None

    def find_map(self, key: Hashable) -> Product:
        """
        Find a product in the filled map based on one of its identifying hash
        keys, or create an empty product with only properties deduced from the
        hash key. Raises a `TypeError` if the hash is not useful for deducing.
        """

        if self._map is not None and key in self._map:
            return self._map[key]

        if isinstance(key, tuple) and len(key) >= 2:
            if key[0] == MapKey.MAP_MATCH and isinstance(key[1], tuple) and \
                len(key[1]) == 4:
                return Product(shop=str(key[1][0]),
                               labels=[
                                   LabelMatch(name=str(label))
                                   for label in key[1][1]
                               ],
                               prices=[
                                   PriceMatch(indicator=str(price[0])
                                              if price[0] is not None else None,
                                              value=Price(price[1]))
                                   for price in key[1][2]
                               ],
                               discounts=[
                                   DiscountMatch(label=str(label))
                                   for label in key[1][3]
                               ])
            if key[0] in {MapKey.MAP_SKU, MapKey.MAP_GTIN} and len(key) == 3:
                product = Product(shop=str(key[1]))
                setattr(product, key[0].value, key[2])
                return product

        raise TypeError("Cannot construct empty Product metadata from key of "
                        f"unexpected type or length: {key!r}")

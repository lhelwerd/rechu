"""
Product metadata matcher.
"""

from collections.abc import Collection, Hashable, Iterator, Sequence, Set
from enum import Enum
import logging
from typing import Optional, Union, cast
from typing_extensions import override
from sqlalchemy import and_, or_, cast as cast_, literal, select, Row, Select, \
    String
from sqlalchemy.orm import aliased, Session
from sqlalchemy.sql.expression import extract
from sqlalchemy.sql.functions import coalesce
from .base import Matcher
from ..models.base import GTIN, Price, Quantity
from ..models.product import Product, LabelMatch, PriceMatch, DiscountMatch
from ..models.receipt import Receipt, ProductItem, Discount, DiscountItems

LOGGER = logging.getLogger(__name__)

class MapKey(str, Enum):
    """
    Keys for a map of products with unique matchers and identifiers.
    """

    MAP_MATCH = 'match'
    MAP_SKU = 'sku'
    MAP_GTIN = 'gtin'

class Indicator(str, Enum):
    """
    Price indicators that are not dates or units.
    """

    MINIMUM = 'minimum'
    MAXIMUM = 'maximum'

_Row = tuple[ProductItem, Product]
class _CandidateRow(Row[_Row]):
    ProductItem: ProductItem
    Product: Product

_MAP_KEYS = frozenset({MapKey.MAP_MATCH, MapKey.MAP_SKU, MapKey.MAP_GTIN})
MapMatch = Union[tuple[str, Optional[Union[str, GTIN]]],
                 tuple[str, tuple[str, ...],
                       tuple[tuple[Optional[str], Price], ...],
                       tuple[str, ...]]]
Key = tuple[MapKey, MapMatch]

class ProductMatcher(Matcher[ProductItem, Product]):
    """
    Matcher for receipt product items and product metadata.
    """

    def __init__(self, map_keys: Set[MapKey] = _MAP_KEYS) -> None:
        super().__init__()
        self.discounts: bool = True
        self._map_keys: Set[MapKey] = map_keys
        self._map: Optional[dict[Hashable, Product]] = None

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

    @override
    def select_duplicate(self, candidate: Product,
                         duplicate: Optional[Product]) -> Optional[Product]:
        if duplicate is not None:
            product_id = cast(Optional[int], candidate.id)
            if product_id is not None and product_id == duplicate.id:
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
        products = self.select_candidates(session, exclude=extra)
        for item in items:
            if only_unmatched and item.product_id is not None:
                continue
            for product in products:
                yield from self._propose(product, item)
            yield from self._propose_extra(item, extra)

    @override
    def find_candidates(self, session: Session,
                        items: Collection[ProductItem] = (),
                        extra: Collection[Product] = (),
                        only_unmatched: bool = False) \
            -> Iterator[tuple[Product, ProductItem]]:
        if any(cast(Optional[int], item.id) is None or item in session.dirty
               for item in items):
            yield from self._find_dirty_candidates(session, items, extra,
                                                   only_unmatched)
            return

        query: Select[_Row] = self._build_query(items, extra, only_unmatched)
        LOGGER.debug('%s', query)
        seen: set[ProductItem] = set()
        extra_ids = {
            product.id for product in extra
            if cast(Optional[int], product.id) is not None
        }
        result = cast(Iterator[_CandidateRow], iter(session.execute(query)))
        for row in result:
            if cast(Optional[Product], row.Product) is not None and \
                row.Product.id not in extra_ids:
                yield from self._propose(row.Product, row.ProductItem)
            if row.ProductItem not in seen:
                seen.add(row.ProductItem)
                yield from self._propose_extra(row.ProductItem, extra)

    def _build_query(self, items: Collection[ProductItem],
                     extra: Collection[Product],
                     only_unmatched: bool) -> Select[_Row]:
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
                         other.indicator == cast_(extract("year", Receipt.date),
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
                                             .notin_((Indicator.MINIMUM,
                                                      Indicator.MAXIMUM))),
                  isouter=True) \
            .join(minimum,
                  Product.prices.and_(minimum.indicator == Indicator.MINIMUM),
                  isouter=True) \
            .join(maximum,
                  Product.prices.and_(maximum.indicator == Indicator.MAXIMUM),
                  isouter=True)
        if not extra:
            query = query.join(ProductItem, item_join)
        query = query.join(Receipt, ProductItem.receipt
                           .and_(Receipt.shop == coalesce(Product.shop,
                                                          Receipt.shop))
                           .and_(price_join))
        if self.discounts:
            discount_join = and_(Discount.id == DiscountItems.discount_id,
                                 Discount.label == coalesce(DiscountMatch.label,
                                                            Discount.label))
            query = query.join(DiscountMatch, Product.discounts, isouter=True) \
                .join(DiscountItems,
                      ProductItem.id == DiscountItems.product_id,
                      isouter=True) \
                .join(Discount, discount_join, isouter=True)
        if items:
            query = query \
                .filter(ProductItem.id.in_(item.id for item in items))
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
        if (price.indicator == Indicator.MINIMUM and
            match_price <= item.price) or \
           (price.indicator == Indicator.MAXIMUM and
            match_price >= item.price):
            return 1
        if (price.indicator is None or
            price.indicator == str(item.receipt.date.year)) and \
            match_price == item.price:
            return 2

        return 0

    @override
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
    def _get_product_match(product: Product) -> Optional[MapMatch]:
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

    @override
    def get_keys(self, product: Product) -> Iterator[Key]:
        keys = (
            (MapKey.MAP_MATCH, self._get_product_match(product)),
            (MapKey.MAP_SKU, (product.shop, product.sku)),
            (MapKey.MAP_GTIN, (product.shop, product.gtin))
        )
        return (
            (map_key, match) for map_key, match in keys
            if map_key in self._map_keys and match is not None and
            match[-1] is not None
        )

    @override
    def select_candidates(self, session: Session,
                          exclude: Collection[Product] = ()) \
            -> Sequence[Product]:
        exclude_ids = {
            product.id for product in exclude
            if cast(Optional[int], product.id) is not None
        }
        return session.scalars(select(Product)
                               .filter(Product.id.notin_(exclude_ids))
                               .order_by(Product.generic_id.asc().nulls_first(),
                                         Product.id)).all()

    @override
    def add_map(self, candidate: Product) -> bool:
        if self._map is None:
            return False

        add = super().add_map(candidate)

        for product_range in candidate.range:
            add = self.add_map(product_range) or add

        return add

    @override
    def discard_map(self, candidate: Product) -> bool:
        if self._map is None:
            return False

        remove = super().discard_map(candidate)

        for product_range in candidate.range:
            remove = self.discard_map(product_range) or remove

        return remove

    @override
    def check_map(self, candidate: Product) -> Optional[Product]:
        if self._map is None:
            return None

        has_keys = False
        for key in self.get_keys(candidate):
            has_keys = True
            if key in self._map:
                return self._map[key]

        if not has_keys:
            for product_range in candidate.range:
                if found_range := super().check_map(product_range):
                    return found_range.generic

        return None

    @staticmethod
    def _deduce_key(key: Hashable) -> bool:
        try:
            return isinstance(key, tuple) and isinstance(key[0], MapKey) and \
                isinstance(key[1], tuple)
        except IndexError:
            return False

    @override
    def find_map(self, key: Hashable) -> Product:
        """
        Find a product in the filled map based on one of its identifying hash
        keys, or create an empty product with only properties deduced from the
        hash key. Raises a `TypeError` if the hash is not useful for deducing.
        """

        if self._map is not None and key in self._map:
            return self._map[key]

        if self._deduce_key(key):
            map_key, match = cast(Key, key)
            if map_key == MapKey.MAP_MATCH and len(match) == 4:
                return Product(shop=str(match[0]),
                               labels=[
                                   LabelMatch(name=str(label))
                                   for label in match[1]
                               ],
                               prices=[
                                   PriceMatch(indicator=str(price[0])
                                              if price[0] is not None else None,
                                              value=Price(price[1]))
                                   for price in match[2]
                               ],
                               discounts=[
                                   DiscountMatch(label=str(label))
                                   for label in match[3]
                               ])
            if map_key in {MapKey.MAP_SKU, MapKey.MAP_GTIN} and len(match) == 2:
                product = Product(shop=str(match[0]))
                setattr(product, map_key.value, match[1])
                return product

        raise TypeError("Cannot construct empty Product metadata from key " +
                        f"of unexpected type or length: {key!r}")

"""
Product metadata matcher.
"""

from collections.abc import Collection, Hashable, Iterator
from itertools import chain
import logging
from typing import Optional
from sqlalchemy import and_, or_, cast, literal, select, Select, String
from sqlalchemy.orm import aliased, Session
from sqlalchemy.sql.expression import extract
from sqlalchemy.sql.functions import coalesce
from .base import Matcher
from ..models.base import Quantity
from ..models.product import Product, LabelMatch, PriceMatch, DiscountMatch
from ..models.receipt import Receipt, ProductItem, Discount, DiscountItems

class ProductMatcher(Matcher[ProductItem, Product]):
    """
    Matcher for receipt product items and product metadata.
    """

    IND_MINIMUM = 'minimum'
    IND_MAXIMUM = 'maximum'

    MAP_MATCH = 'match'
    MAP_SKU = 'sku'
    MAP_GTIN = 'gtin'

    def __init__(self) -> None:
        super().__init__()
        self.discounts = True

    def _propose(self, product: Product,
                 item: ProductItem) -> Iterator[tuple[Product, ProductItem]]:
        if self.match(product, item):
            yield product, item

    def _find_dirty_candidates(self, session: Session,
                               items: Collection[ProductItem],
                               extra: Optional[Collection[Product]],
                               only_unmatched: bool = False) \
            -> Iterator[tuple[Product, ProductItem]]:
        products = session.scalars(select(Product).order_by(Product.id)) \
            .all()
        for item in items:
            if only_unmatched and item.product_id is not None:
                continue
            for product in chain(products, extra if extra is not None else []):
                yield from self._propose(product, item)

    def find_candidates(self, session: Session,
                        items: Optional[Collection[ProductItem]] = None,
                        extra: Optional[Collection[Product]] = None,
                        only_unmatched: bool = False) \
            -> Iterator[tuple[Product, ProductItem]]:
        if items is not None and \
            any(item.id is None or item in session.dirty for item in items):
            yield from self._find_dirty_candidates(session, items, extra,
                                                   only_unmatched)
            return

        query = self._build_query(items, extra, only_unmatched)
        logging.warning('%s', query)
        seen = set()
        for row in session.execute(query):
            if row.Product is not None:
                yield from self._propose(row.Product, row.ProductItem)
            if extra is not None and row.ProductItem not in seen:
                seen.add(row.ProductItem)
                for product in extra:
                    yield from self._propose(product, row.ProductItem)

    def _build_query(self, items: Optional[Collection[ProductItem]],
                     extra: Optional[Collection[Product]],
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
        if extra is None:
            query = query.select_from(Product)
        else:
            query = query.select_from(ProductItem) \
                .join(Product, literal(value=True), isouter=True) \
                .filter(item_join)
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
        if extra is None:
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
        if items is not None:
            query = query \
                .filter(ProductItem.id.in_((item.id for item in items)))
        if only_unmatched:
            query = query.filter(ProductItem.product_id.is_(None))
        query = query.order_by(ProductItem.id, Product.id)

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
        return (
            (self.MAP_MATCH, self._get_product_match(product)),
            (self.MAP_SKU, product.shop, product.sku),
            (self.MAP_GTIN, product.shop, product.gtin)
        )

    def load_map(self, session: Session) -> None:
        self._map = {}
        for product in session.scalars(select(Product)):
            self.add_map(product)

    def add_map(self, candidate: Product) -> bool:
        if self._map is None:
            return False

        add = False
        for key in self._get_keys(candidate):
            if key[-1] is not None:
                add = self._map.setdefault(key, candidate) is candidate or add

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
                logging.warning('Product instance stored at %r is not %r: %r',
                                key, candidate, product)
                self._map[key] = product

        return remove

    def check_map(self, candidate: Product) -> Optional[Product]:
        if self._map is None:
            return None
        for key in self._get_keys(candidate):
            if key in self._map:
                return self._map[key]
        return None

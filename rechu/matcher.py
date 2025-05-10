"""
Database entity matching methods.
"""

from collections.abc import Iterable, Iterator, Sequence
from datetime import date
import logging
from typing import Generic, Optional, TypeVar
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import aliased, Session
from sqlalchemy.sql.functions import coalesce
from .models.base import Price
from .models.product import Product, LabelMatch, PriceMatch, DiscountMatch
from .models.receipt import Receipt, ProductItem, Discount, DiscountItems

IT = TypeVar('IT')
CT = TypeVar('CT')

class Matcher(Generic[IT, CT]):
    """
    Generic item candidate model matcher.
    """

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

class ProductMatcher(Matcher[ProductItem, Product]):
    """
    Matcher for receipt product items and product metadata.
    """

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
                if self._match(product, item):
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
                                             .notin_(('minimum', 'maximum'))),
                  isouter=True) \
            .join(minimum, Product.prices.and_(minimum.indicator == 'minimum'),
                  isouter=True) \
            .join(maximum, Product.prices.and_(maximum.indicator == 'maximum'),
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
            if self._match(row.Product, row.ProductItem):
                yield row.Product, row.ProductItem

    @staticmethod
    def _match_price(price: PriceMatch, item_value: Price,
                     item_date: date) -> int:
        if (price.indicator == 'minimum' and price.value <= item_value) or \
           (price.indicator == 'maximum' and price.value >= item_value):
            return 1
        if (price.indicator is None or
            price.indicator == str(item_date.year)) and \
            price.value == item_value:
            return 2

        return 0

    def _match(self, product: Product, item: ProductItem) -> bool:
        if product.shop != item.receipt.shop:
            return False
        if product.labels and \
            all(label.name != item.label for label in product.labels):
            return False

        seen_price = 0
        item_price = Price(item.price)
        for price in product.prices:
            seen_price += self._match_price(price, item_price,
                                            item.receipt.date)
        # Must adhere to both 'minimum' and 'maximum', one date indicator or
        # no indicator
        if product.prices and seen_price < 2:
            return False

        for discount in product.discounts:
            if all(discount.label != bonus.label for bonus in item.discounts):
                return False

        return True

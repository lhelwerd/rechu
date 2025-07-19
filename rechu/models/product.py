"""
Models for product metadata.
"""

from itertools import zip_longest
import logging
from typing import Optional
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import MappedColumn, Relationship, mapped_column, \
    relationship
from .base import Base, GTIN, Price, Quantity

LOGGER = logging.getLogger(__name__)

_CASCADE_OPTIONS = "all, delete-orphan"
_PRODUCT_REF = "product.id"

class Product(Base): # pylint: disable=too-few-public-methods
    """
    Product model for metadata.
    """

    __tablename__ = "product"

    id: MappedColumn[int] = mapped_column(primary_key=True, autoincrement=True)
    shop: MappedColumn[str] = mapped_column(String(32)) # shop.key

    # Matchers
    labels: Relationship[list["LabelMatch"]] = \
        relationship(back_populates="product", cascade=_CASCADE_OPTIONS,
                     passive_deletes=True, lazy="selectin")
    prices: Relationship[list["PriceMatch"]] = \
        relationship(back_populates="product", cascade=_CASCADE_OPTIONS,
                     passive_deletes=True, lazy="selectin")
    discounts: Relationship[list["DiscountMatch"]] = \
        relationship(back_populates="product", cascade=_CASCADE_OPTIONS,
                     passive_deletes=True, lazy="selectin")

    # Descriptors
    brand: MappedColumn[Optional[str]]
    description: MappedColumn[Optional[str]]

    # Taxonomy
    category: MappedColumn[Optional[str]]
    type: MappedColumn[Optional[str]]

    # Trade item properties
    portions: MappedColumn[Optional[int]]
    weight: MappedColumn[Optional[Quantity]]
    volume: MappedColumn[Optional[Quantity]]
    alcohol: MappedColumn[Optional[str]]

    # Shop-specific and globally unique identifiers
    sku: MappedColumn[Optional[str]]
    gtin: MappedColumn[Optional[GTIN]]

    # Product range differentiation
    range: Relationship[list["Product"]] = \
        relationship(back_populates="generic", cascade=_CASCADE_OPTIONS,
                     passive_deletes=True, order_by="Product.id",
                     lazy="selectin")
    generic_id: MappedColumn[Optional[int]] = \
        mapped_column(ForeignKey(_PRODUCT_REF, ondelete="CASCADE"))
    generic: Relationship[Optional["Product"]] = \
        relationship(back_populates="range", remote_side=[id], lazy="selectin")

    def clear(self) -> None:
        """
        Remove all matchers, properties, identifiers and range products, but
        not the generic product or its properties that we inherit now.
        """

        self.labels = []
        self.prices = []
        self.discounts = []
        self.range = []
        for column, meta in self.__table__.c.items():
            if meta.nullable and not meta.foreign_keys:
                setattr(self, column, None)

        # Obtain inherited default properties
        if self.generic is not None:
            self.merge(self.generic)
            self.sku = None
            self.gtin = None

    def replace(self, new: "Product") -> None:
        """
        Replace all matchers, properties, identifiers and range products with
        those defined in the `new` product, or with the generic product's
        inherited properties; the original generic product is kept.
        """

        self.clear()

        # Clear matchers obtained from generic product in favor of overrides
        if self.generic is not None:
            if new.labels:
                self.labels = []
            if new.prices:
                self.prices = []
            if new.discounts:
                self.discounts = []

        self.merge(new)

    def copy(self) -> "Product":
        """
        Copy the product.
        """

        copy = Product(shop=self.shop)
        copy.merge(self)
        return copy

    def check_merge(self, other: "Product") -> None:
        """
        Check if the other product is compatible with merging into this product.
        """

        if self.prices and other.prices:
            plain = any(price.indicator is None for price in self.prices)
            other_plain = any(price.indicator is None for price in other.prices)
            if plain ^ other_plain:
                raise ValueError("Both products' price matchers must have "
                                 "indicators, or none of theirs should: "
                                 f"{self!r} {other!r}")
        for product_range, other_range in zip(self.range, other.range):
            product_range.check_merge(other_range)

    def _merge_range(self, other: "Product", override: bool = True) -> bool:
        changed = False
        if self.generic is None:
            for sub_range, other_range in zip_longest(self.range, other.range):
                if sub_range is None:
                    LOGGER.debug('Adding range product %r', other_range)
                    self.range.append(other_range.copy())
                    changed = True
                elif other_range is not None and \
                    sub_range.merge(other_range, override=override):
                    LOGGER.debug('Merged range products')
                    changed = True

        return changed

    def _merge_fields(self, other: "Product", override: bool = True) -> bool:
        changed = False
        for column, meta in self.__table__.c.items():
            current = getattr(self, column)
            if meta.foreign_keys or (current is not None and not override):
                LOGGER.debug('Not updating field %s (%r)', column, current)
                continue

            target = getattr(other, column)
            if (meta.nullable or (meta.primary_key and current is None)) and \
                target is not None and current != target:
                LOGGER.debug('Updating field %s from %r to %r', column,
                              current, target)
                setattr(self, column, target)
                changed = True

        return changed

    def merge(self, other: "Product", override: bool = True) -> bool:
        """
        Merge attributes of the other product into this one.

        This replaces values and the primary key in this product, except for the
        shop identifier (which is always kept) and the matchers (where unique
        matchers from the other product are added).

        This is similar to a session merge except no database changes are done
        and the matchers are more deeply merged.

        If `override` is disabled, then simple property fields that already have
        a value are not changed. Matchers are always updated.

        Returns whether the product has changed, with new matchers or different
        values.
        """

        self.check_merge(other)

        LOGGER.debug('Performing merge into %r from %r', self, other)
        changed = False
        labels = {label.name for label in self.labels}
        for label in other.labels:
            if label.name not in labels:
                LOGGER.debug('Adding label matcher %s', label.name)
                self.labels.append(LabelMatch(name=label.name))
                changed = True
        prices = {(price.indicator, price.value) for price in self.prices}
        for price in other.prices:
            if (price.indicator, price.value) not in prices:
                LOGGER.debug('Adding price matcher %r (indicator: %r)',
                             price.value, price.indicator)
                self.prices.append(PriceMatch(indicator=price.indicator,
                                              value=price.value))
                changed = True
        discounts = {discount.label for discount in self.discounts}
        for discount in other.discounts:
            if discount.label not in discounts:
                LOGGER.debug('Adding discount matcher %r', discount.label)
                self.discounts.append(DiscountMatch(label=discount.label))
                changed = True

        if self._merge_range(other, override=override):
            changed = True

        if self._merge_fields(other, override=override):
            changed = True

        LOGGER.debug('Merged products: %r', changed)
        return changed

    def __repr__(self) -> str:
        weight = str(self.weight) if self.weight is not None else None
        volume = str(self.volume) if self.volume is not None else None
        sub_range = f", range={self.range!r}" if self.generic is None else ""
        return (f"Product(id={self.id!r}, shop={self.shop!r}, "
                f"labels={self.labels!r}, prices={self.prices!r}, "
                f"discounts={self.discounts!r}, brand={self.brand!r}, "
                f"description={self.description!r}, "
                f"category={self.category!r}, type={self.type!r}, "
                f"portions={self.portions!r}, weight={weight!r}, "
                f"volume={volume!r}, alcohol={self.alcohol!r}, "
                f"sku={self.sku!r}, gtin={self.gtin!r}{sub_range})")

class LabelMatch(Base): # pylint: disable=too-few-public-methods
    """
    Label model for a product matching string.
    """

    __tablename__ = "product_label_match"

    id: MappedColumn[int] = mapped_column(primary_key=True)
    product_id: MappedColumn[int] = \
        mapped_column(ForeignKey(_PRODUCT_REF, ondelete='CASCADE'))
    product: Relationship[Product] = relationship(back_populates="labels")
    name: MappedColumn[str]

    def __repr__(self) -> str:
        return repr(self.name)

class PriceMatch(Base): # pylint: disable=too-few-public-methods
    """
    Price model for a product matching value, which may be part of a value range
    or time interval.
    """

    __tablename__ = "product_price_match"

    id: MappedColumn[int] = mapped_column(primary_key=True)
    product_id: MappedColumn[int] = \
        mapped_column(ForeignKey(_PRODUCT_REF, ondelete='CASCADE'))
    product: Relationship[Product] = relationship(back_populates="prices")
    value: MappedColumn[Price]
    indicator: MappedColumn[Optional[str]]

    def __repr__(self) -> str:
        return str(self.value) if self.indicator is None else \
            f"({self.indicator!r}, {self.value!s})"

class DiscountMatch(Base): # pylint: disable=too-few-public-methods
    """
    Discount label model for a product matching string.
    """

    __tablename__ = "product_discount_match"

    id: MappedColumn[int] = mapped_column(primary_key=True)
    product_id: MappedColumn[int] = \
        mapped_column(ForeignKey(_PRODUCT_REF, ondelete='CASCADE'))
    product: Relationship[Product] = relationship(back_populates="discounts")
    label: MappedColumn[str]

    def __repr__(self) -> str:
        return repr(self.label)

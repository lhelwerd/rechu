"""
Models for product metadata.
"""

from typing import Optional
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, GTIN, Price

_CASCADE_OPTIONS = "all, delete-orphan"
_PRODUCT_REF = "product.id"

class Product(Base): # pylint: disable=too-few-public-methods
    """
    Product model for metadata.
    """

    __tablename__ = "product"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    shop: Mapped[str] = mapped_column(String(32)) # shop.key

    # Matchers
    labels: Mapped[list["LabelMatch"]] = \
        relationship(back_populates="product", cascade=_CASCADE_OPTIONS,
                     passive_deletes=True)
    prices: Mapped[list["PriceMatch"]] = \
        relationship(back_populates="product", cascade=_CASCADE_OPTIONS,
                     passive_deletes=True)
    discounts: Mapped[list["DiscountMatch"]] = \
        relationship(back_populates="product", cascade=_CASCADE_OPTIONS,
                     passive_deletes=True)

    # Descriptors
    brand: Mapped[Optional[str]]
    description: Mapped[Optional[str]]

    # Taxonomy
    category: Mapped[Optional[str]]
    type: Mapped[Optional[str]]

    # Trade item properties
    portions: Mapped[Optional[int]]
    weight: Mapped[Optional[str]]
    volume: Mapped[Optional[str]]
    alcohol: Mapped[Optional[str]]

    # Shop-specific and globally unique identifiers
    sku: Mapped[Optional[str]]
    gtin: Mapped[Optional[GTIN]]

    def _check_merge(self, other: "Product") -> None:
        if self.prices and other.prices:
            plain = any(price.indicator is None for price in self.prices)
            other_plain = any(price.indicator is None for price in other.prices)
            if plain ^ other_plain:
                raise ValueError("Both products' price matchers must have "
                                 "indicators, or none of theirs should: "
                                 f"{self!r} {other!r}")

    def merge(self, other: "Product") -> bool:
        """
        Merge attributes of the other product into this one.

        This replaces values and the primary key in this product, except for the
        shop identifier (which is always kept) and the matchers (where unique
        matchers from the other product are added).

        This is similar to a session merge except no database changes are done
        and the matchers are more deeply merged.

        Returns whether the product has changed, with new matchers or different
        values.
        """

        self._check_merge(other)

        changed = False
        labels = {label.name for label in self.labels}
        for label in other.labels:
            if label.name not in labels:
                self.labels.append(LabelMatch(name=label.name))
                changed = True
        prices = {(price.indicator, price.value) for price in self.prices}
        for price in other.prices:
            if (price.indicator, price.value) not in prices:
                self.prices.append(PriceMatch(indicator=price.indicator,
                                              value=price.value))
                changed = True
        discounts = {discount.label for discount in self.discounts}
        for discount in other.discounts:
            if discount.label not in discounts:
                self.discounts.append(DiscountMatch(label=discount.label))
                changed = True

        for column, meta in self.__table__.c.items():
            current = getattr(self, column)
            target = getattr(other, column)
            if (meta.nullable or (meta.primary_key and current is None)) and \
                target is not None and current != target:
                setattr(self, column, target)
                changed = True

        return changed

    def __repr__(self) -> str:
        return (f"Product(id={self.id!r}, shop={self.shop!r}, "
                f"labels={self.labels!r}, prices={self.prices!r}, "
                f"discounts={self.discounts!r}, brand={self.brand!r}, "
                f"description={self.description!r}, "
                f"category={self.category!r}, type={self.type!r}, "
                f"portions={self.portions!r}, weight={self.weight!r}, "
                f"volume={self.volume!r}, alcohol={self.alcohol!r}, "
                f"sku={self.sku!r}, gtin={self.gtin!r})")

class LabelMatch(Base): # pylint: disable=too-few-public-methods
    """
    Label model for a product matching string.
    """

    __tablename__ = "product_label_match"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey(_PRODUCT_REF,
                                                       ondelete='CASCADE'))
    product: Mapped[Product] = relationship(back_populates="labels")
    name: Mapped[str]

    def __repr__(self) -> str:
        return repr(self.name)

class PriceMatch(Base): # pylint: disable=too-few-public-methods
    """
    Price model for a product matching value, which may be part of a value range
    or time interval.
    """

    __tablename__ = "product_price_match"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey(_PRODUCT_REF,
                                                       ondelete='CASCADE'))
    product: Mapped[Product] = relationship(back_populates="prices")
    value: Mapped[Price]
    indicator: Mapped[Optional[str]]

    def __repr__(self) -> str:
        return repr(self.value) if self.indicator is None else \
            repr((self.indicator, self.value))

class DiscountMatch(Base): # pylint: disable=too-few-public-methods
    """
    Discount label model for a product matching string.
    """

    __tablename__ = "product_discount_match"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey(_PRODUCT_REF,
                                                       ondelete='CASCADE'))
    product: Mapped[Product] = relationship(back_populates="discounts")
    label: Mapped[str]

    def __repr__(self) -> str:
        return repr(self.label)

"""
Models for product metadata.
"""

import logging
from enum import Enum
from itertools import zip_longest
from typing import Any, TypeVar, cast, final

from sqlalchemy import ForeignKey
from sqlalchemy.orm import (
    MappedColumn,
    Relationship,
    mapped_column,
    relationship,
)
from sqlalchemy.sql.elements import KeyedColumnElement
from typing_extensions import override

from .base import GTIN, Base, Price, Quantity
from .shop import Shop

T = TypeVar("T")
Indicators = dict[str | Price | None, "PriceMatch"]

LOGGER = logging.getLogger(__name__)

_CASCADE_OPTIONS = "all, delete-orphan"
_PRODUCT_REF = "product.id"


class Indicator(str, Enum):
    """
    Price matcher indicators that are not dates or units.
    """

    MINIMUM = "minimum"
    MAXIMUM = "maximum"


@final
class Product(Base):
    """
    Product model for metadata.
    """

    __tablename__ = "product"

    id: MappedColumn[int] = mapped_column(primary_key=True, autoincrement=True)
    shop: MappedColumn[str] = mapped_column(ForeignKey("shop.key"))
    shop_meta: Relationship[Shop] = relationship()

    # Matchers
    labels: Relationship[list["LabelMatch"]] = relationship(
        back_populates="product",
        cascade=_CASCADE_OPTIONS,
        passive_deletes=True,
        lazy="selectin",
    )
    prices: Relationship[list["PriceMatch"]] = relationship(
        back_populates="product",
        cascade=_CASCADE_OPTIONS,
        passive_deletes=True,
        lazy="selectin",
    )
    discounts: Relationship[list["DiscountMatch"]] = relationship(
        back_populates="product",
        cascade=_CASCADE_OPTIONS,
        passive_deletes=True,
        lazy="selectin",
    )

    # Descriptors
    brand: MappedColumn[str | None] = mapped_column()
    description: MappedColumn[str | None] = mapped_column()

    # Taxonomy
    category: MappedColumn[str | None] = mapped_column()
    type: MappedColumn[str | None] = mapped_column()

    # Trade item properties
    portions: MappedColumn[int | None] = mapped_column()
    weight: MappedColumn[Quantity | None] = mapped_column()
    volume: MappedColumn[Quantity | None] = mapped_column()
    alcohol: MappedColumn[str | None] = mapped_column()

    # Shop-specific and globally unique identifiers
    sku: MappedColumn[str | None] = mapped_column()
    gtin: MappedColumn[GTIN | None] = mapped_column()

    # Product range differentiation
    range: Relationship[list["Product"]] = relationship(
        back_populates="generic",
        cascade=_CASCADE_OPTIONS,
        passive_deletes=True,
        order_by="Product.id",
        lazy="selectin",
        join_depth=2,
    )
    generic_id: MappedColumn[int | None] = mapped_column(
        ForeignKey(_PRODUCT_REF, ondelete="CASCADE")
    )
    generic: Relationship["Product | None"] = relationship(
        back_populates="range", remote_side=[id], lazy="selectin", join_depth=2
    )

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
            if cast(bool, meta.nullable) and not meta.foreign_keys:
                setattr(self, column, None)

        # Obtain inherited default properties
        if self.generic is not None:
            _ = self.merge(self.generic)
            self.sku = None
            self.gtin = None

    def replace(self, new: "Product") -> bool:
        """
        Replace all matchers, properties, identifiers and range products with
        those defined in the `new` product, or with the generic product's
        inherited properties; the original generic product is kept.

        Returns whether the new product is not empty.
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

        return self.merge(new)

    def copy(self) -> "Product":
        """
        Copy the product.
        """

        copy = Product(shop=self.shop)
        _ = copy.merge(self)
        return copy

    def check_merge(self, other: "Product") -> None:
        """
        Check if the other product is compatible with merging into this product.
        """

        if self.shop != other.shop:
            raise ValueError(
                "Both products must be for the same shop: "
                + f"{self.shop!r} != {other.shop!r}"
            )

        # Check if existing products in range are compatible when merging
        for product_range, other_range in zip(
            self.range, other.range, strict=False
        ):
            product_range.check_merge(other_range)

    def _merge_range(self, other: "Product", replace: bool = True) -> bool:
        changed = False
        if self.generic is None:
            for sub_range, other_range in zip_longest(self.range, other.range):
                if sub_range is None:
                    LOGGER.debug("Adding range product %r", other_range)
                    self.range.append(other_range.copy())
                    changed = True
                elif other_range is not None and sub_range.merge(
                    other_range, replace=replace
                ):
                    LOGGER.debug("Merged range products")
                    changed = True

        return changed

    def _merge_field(
        self,
        column: str,
        values: tuple[T | None, T | None],
        meta: KeyedColumnElement[Any],
        replace: bool = True,
    ) -> bool:
        current, target = values
        if meta.foreign_keys or (current is not None and not replace):
            LOGGER.debug("Not updating field %s (%r)", column, current)
            return False

        if (
            (
                cast(bool, meta.nullable)
                or (meta.primary_key and current is None)
            )
            and target is not None
            and current != target
        ):
            LOGGER.debug(
                "Updating field %s from %r to %r", column, current, target
            )
            setattr(self, column, target)
            return not meta.primary_key

        return False

    def _merge_fields(self, other: "Product", replace: bool = True) -> bool:
        changed = False
        for column, meta in self.__table__.c.items():
            changed = (
                self._merge_field(
                    column,
                    (getattr(self, column, None), getattr(other, column, None)),
                    meta,
                    replace=replace,
                )
                or changed
            )

        return changed

    def _merge_price(
        self,
        other: "Product",
        price: "PriceMatch",
        indicators: Indicators,
        plain: bool,
    ) -> tuple[bool, bool]:
        changed = False
        indicator = price.indicator
        if indicator is None:
            if plain:
                changed = self._merge_price_indicators(
                    PriceMatch(indicator=None, value=Price(price.value)),
                    indicators,
                )
            else:
                # Adjust price to have indicator based on existing indicators
                for adjust in self._adjust_price(price.value, indicators):
                    changed = (
                        self._merge_price_indicators(adjust, indicators)
                        or changed
                    )
        else:
            if plain:
                # Adjust prices to have indicators based on other indicators
                changed = self._adjust_prices(other)
                plain = False

            changed = self._merge_price_indicators(price, indicators) or changed

        return changed, plain

    def _make_price_indicators(self) -> tuple[Indicators, bool]:
        indicators: Indicators = {}
        plain = True
        for price in self.prices:
            if price.indicator is None:
                indicators[price.value] = price
            else:
                plain = False
                indicators[price.indicator] = price

        return indicators, plain

    def _merge_price_indicators(
        self, price: "PriceMatch", indicators: Indicators
    ) -> bool:
        indicator = price.indicator
        if indicator in indicators:
            merge = indicators[indicator]
            # Avoid duplicate indicator by merging ranges (if different)
            match (indicator, price.value):
                case (_, merge.value):
                    return False
                case (Indicator.MAXIMUM, _):
                    merge.value = max(merge.value, price.value)
                case (Indicator.MINIMUM, _):
                    merge.value = min(merge.value, price.value)
                case _:
                    LOGGER.warning(
                        "Overriding price matcher %r=%r with %r",
                        indicator,
                        merge.value,
                        price.value,
                    )
                    merge.value = price.value

            return True

        if indicator is not None or price.value not in indicators:
            LOGGER.debug(
                "Adding price matcher %r (indicator: %r)",
                price.value,
                indicator,
            )
            self.prices.append(
                PriceMatch(indicator=indicator, value=Price(price.value))
            )
            return True

        return False

    def _adjust_prices(self, other: "Product") -> bool:
        plain = True
        new_prices = (
            self._adjust_price(
                own.value,
                {other.indicator: other for other in other.prices},
            )
            for own in self.prices
        )
        self.prices = []
        for new_price in new_prices:
            indicators, plain = self._make_price_indicators()
            for new in new_price:
                _ = self._merge_price_indicators(new, indicators)
        return not plain

    def _adjust_price(
        self, price: Price, indicators: Indicators
    ) -> list["PriceMatch"]:
        price = Price(price)
        if Indicator.MINIMUM in indicators:
            return [PriceMatch(indicator=Indicator.MINIMUM.value, value=price)]
        if Indicator.MAXIMUM in indicators:
            return [PriceMatch(indicator=Indicator.MAXIMUM.value, value=price)]

        return [
            PriceMatch(indicator=Indicator.MINIMUM.value, value=price),
            PriceMatch(indicator=Indicator.MAXIMUM.value, value=price),
        ]

    def merge(self, other: "Product", replace: bool = True) -> bool:
        """
        Merge attributes of the other product into this one.

        This replaces values and the primary key in this product, except for the
        shop identifier (which must be the same) and the matchers (where unique
        matchers from the other product are added).

        This is similar to a session merge except no database changes are done
        and the matchers are more deeply merged.

        If `replace` is disabled, then simple property fields that already have
        a value are not changed. Matchers are always updated.

        Returns whether the product has changed, with new matchers or different
        values.
        """

        self.check_merge(other)

        LOGGER.debug("Performing merge into %r from %r", self, other)
        changed = False
        labels = {label.name for label in self.labels}
        for label in other.labels:
            if label.name not in labels:
                LOGGER.debug("Adding label matcher %s", label.name)
                self.labels.append(LabelMatch(name=label.name))
                changed = True

        indicators, plain = self._make_price_indicators()
        for price in other.prices:
            changed, plain = self._merge_price(other, price, indicators, plain)

        discounts = {discount.label for discount in self.discounts}
        for discount in other.discounts:
            if discount.label not in discounts:
                LOGGER.debug("Adding discount matcher %r", discount.label)
                self.discounts.append(DiscountMatch(label=discount.label))
                changed = True

        if self._merge_range(other, replace=replace):
            changed = True

        if self._merge_fields(other, replace=replace):
            changed = True

        LOGGER.debug("Merged products: %r", changed)
        return changed

    @override
    def __repr__(self) -> str:
        weight = str(self.weight) if self.weight is not None else None
        volume = str(self.volume) if self.volume is not None else None
        sub_range = f", range={self.range!r}" if self.generic is None else ""
        return (
            f"Product(id={self.id!r}, shop={self.shop!r}, "
            f"labels={self.labels!r}, prices={self.prices!r}, "
            f"discounts={self.discounts!r}, brand={self.brand!r}, "
            f"description={self.description!r}, "
            f"category={self.category!r}, type={self.type!r}, "
            f"portions={self.portions!r}, weight={weight!r}, "
            f"volume={volume!r}, alcohol={self.alcohol!r}, "
            f"sku={self.sku!r}, gtin={self.gtin!r}{sub_range})"
        )


class Match:  # pylint: disable=too-few-public-methods
    """
    Model that matches a field of a product.
    """


@final
class LabelMatch(Base, Match):  # pylint: disable=too-few-public-methods
    """
    Label model for a product matching string.
    """

    __tablename__ = "product_label_match"

    id: MappedColumn[int] = mapped_column(primary_key=True)
    product_id: MappedColumn[int] = mapped_column(
        ForeignKey(_PRODUCT_REF, ondelete="CASCADE")
    )
    product: Relationship[Product] = relationship(back_populates="labels")
    name: MappedColumn[str] = mapped_column()

    @override
    def __repr__(self) -> str:
        return repr(self.name)


@final
class PriceMatch(Base, Match):  # pylint: disable=too-few-public-methods
    """
    Price model for a product matching value, which may be part of a value range
    or time interval.
    """

    __tablename__ = "product_price_match"

    id: MappedColumn[int] = mapped_column(primary_key=True)
    product_id: MappedColumn[int] = mapped_column(
        ForeignKey(_PRODUCT_REF, ondelete="CASCADE")
    )
    product: Relationship[Product] = relationship(back_populates="prices")
    value: MappedColumn[Price] = mapped_column()
    indicator: MappedColumn[str | None] = mapped_column()

    @override
    def __repr__(self) -> str:
        return (
            str(self.value)
            if self.indicator is None
            else f"({self.indicator!r}, {self.value!s})"
        )


@final
class DiscountMatch(Base, Match):  # pylint: disable=too-few-public-methods
    """
    Discount label model for a product matching string.
    """

    __tablename__ = "product_discount_match"

    id: MappedColumn[int] = mapped_column(primary_key=True)
    product_id: MappedColumn[int] = mapped_column(
        ForeignKey(_PRODUCT_REF, ondelete="CASCADE")
    )
    product: Relationship[Product] = relationship(back_populates="discounts")
    label: MappedColumn[str] = mapped_column()

    @override
    def __repr__(self) -> str:
        return repr(self.label)

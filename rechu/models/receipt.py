"""
Models for receipt data.
"""

import datetime
import re
from typing import Optional, final
from typing_extensions import override
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import MappedColumn, Relationship, mapped_column, \
    relationship
from .base import Base, Price, Quantity, Unit
from .product import Product
from .shop import Shop

@final
class Receipt(Base):
    """
    Receipt model for a receipt from a certain date at a shop with products
    and possibly discounts.
    """

    __tablename__ = "receipt"

    filename: MappedColumn[str] = mapped_column(String(255), primary_key=True)
    updated: MappedColumn[datetime.datetime] = mapped_column()
    date: MappedColumn[datetime.date] = mapped_column()
    shop: MappedColumn[str] = mapped_column("shop", ForeignKey("shop.key"))
    shop_meta: Relationship[Shop] = relationship()
    products: Relationship[list["ProductItem"]] = \
        relationship(back_populates="receipt", cascade="all, delete-orphan",
                     passive_deletes=True, order_by="ProductItem.position")
    discounts: Relationship[list["Discount"]] = \
        relationship(back_populates="receipt", cascade="all, delete-orphan",
                     passive_deletes=True, order_by="Discount.position")

    @property
    def total_price(self) -> Price:
        """
        Retrieve the total cost of the receipt after discounts.
        """

        total = sum(product.price for product in self.products)
        return Price(total + self.total_discount)

    @property
    def total_discount(self) -> Price:
        """
        Retrieve the total discount of the receipt.
        """

        total = sum(discount.price_decrease for discount in self.discounts)
        return Price(total)

    @override
    def __repr__(self) -> str:
        return (f"Receipt(date={self.date.isoformat()!r}, shop={self.shop!r})")

@final
class DiscountItems(Base): # pylint: disable=too-few-public-methods
    """
    Association table for products involved in discounts.
    """

    __tablename__ = "receipt_discount_products"

    discount_id: MappedColumn[int] = \
        mapped_column("discount_id", ForeignKey('receipt_discount.id',
                                                ondelete='CASCADE'),
                      primary_key=True)
    product_id: MappedColumn[int] = \
        mapped_column("product_id", ForeignKey('receipt_product.id',
                                               ondelete='CASCADE'),
                      primary_key=True)

@final
class ProductItem(Base): # pylint: disable=too-few-public-methods
    """
    Product model for a product item mentioned on a receipt.
    """

    __tablename__ = "receipt_product"

    id: MappedColumn[int] = mapped_column(primary_key=True)
    receipt_key: MappedColumn[str] = \
        mapped_column(ForeignKey('receipt.filename', ondelete='CASCADE'))
    receipt: Relationship[Receipt] = relationship(back_populates="products")

    quantity: MappedColumn[Quantity] = mapped_column()
    label: MappedColumn[str] = mapped_column()
    price: MappedColumn[Price] = mapped_column()
    discount_indicator: MappedColumn[Optional[str]] = mapped_column()
    discounts: Relationship[list["Discount"]] = \
        relationship(secondary=DiscountItems.__table__,
                     back_populates="items",
                     passive_deletes=True)
    product_id: MappedColumn[Optional[int]] = \
        mapped_column(ForeignKey('product.id', ondelete='SET NULL'))
    product: Relationship[Optional[Product]] = relationship()
    position: MappedColumn[int] = mapped_column()
    # Extracted fields from quantity
    amount: MappedColumn[float] = mapped_column()
    unit: MappedColumn[Optional[Unit]] = mapped_column()

    @property
    def discount_indicators(self) -> list[str]:
        """
        Retrieve a list of discrete portions of the discount indicator.
        """

        if self.discount_indicator is None:
            return []

        pattern = '|'.join(
            indicator.pattern
            for indicator in self.receipt.shop_meta.discount_indicators
        )
        return [
            part for part in re.split(rf"({pattern})", self.discount_indicator)
            if part != ""
        ]

    @override
    def __repr__(self) -> str:
        return (f"ProductItem(receipt={self.receipt_key!r}, "
                f"quantity='{self.quantity!s}', label={self.label!r}, "
                f"price={self.price!s}, "
                f"discount_indicator={self.discount_indicator!r}, "
                f"product={self.product_id!r})")

@final
class Discount(Base): # pylint: disable=too-few-public-methods
    """
    Discount model for a discount action mentioned on a receipt.
    """

    __tablename__ = "receipt_discount"

    id: MappedColumn[int] = mapped_column(primary_key=True)
    receipt_key: MappedColumn[str] = \
        mapped_column(ForeignKey('receipt.filename', ondelete='CASCADE'))
    receipt: Relationship[Receipt] = relationship(back_populates="discounts")

    label: MappedColumn[str] = mapped_column()
    price_decrease: MappedColumn[Price] = mapped_column()
    items: Relationship[list[ProductItem]] = \
        relationship(secondary=DiscountItems.__table__,
                     back_populates="discounts",
                     passive_deletes=True)
    position: MappedColumn[int] = mapped_column()

    @override
    def __repr__(self) -> str:
        return (f"Discount(receipt={self.receipt_key!r}, label={self.label!r}, "
                f"price_decrease={self.price_decrease!s}, "
                f"items={[item.label for item in self.items]!r})")

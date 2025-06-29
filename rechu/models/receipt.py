"""
Models for receipt data.
"""

import datetime
from typing import Optional
from sqlalchemy import Column, ForeignKey, String, Table
from sqlalchemy.orm import MappedColumn, Relationship,  mapped_column, \
    relationship
from .base import Base, Price, Quantity, Unit
from .product import Product

class Receipt(Base): # pylint: disable=too-few-public-methods
    """
    Receipt model for a receipt from a certain date at a shop with products
    and possibly discounts.
    """

    __tablename__ = "receipt"

    filename: MappedColumn[str] = mapped_column(String(255), primary_key=True)
    updated: MappedColumn[datetime.datetime]
    date: MappedColumn[datetime.date]
    shop: MappedColumn[str] = mapped_column(String(32)) # shop.key
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

        total = sum(product.price for product in self.products) + \
            sum(discount.price_decrease for discount in self.discounts)
        return Price(total)

    def __repr__(self) -> str:
        return f"Receipt(date={self.date.isoformat()!r}, shop={self.shop!r})"

# Association table for products involved in discounts
DiscountItems = Table("receipt_discount_products", Base.metadata,
                      Column("discount_id", ForeignKey('receipt_discount.id',
                                                       ondelete='CASCADE'),
                             primary_key=True),
                      Column("product_id", ForeignKey('receipt_product.id',
                                                      ondelete='CASCADE'),
                             primary_key=True))

class ProductItem(Base): # pylint: disable=too-few-public-methods
    """
    Product model for a product item mentioned on a receipt.
    """

    __tablename__ = "receipt_product"

    id: MappedColumn[int] = mapped_column(primary_key=True)
    receipt_key: MappedColumn[str] = \
        mapped_column(ForeignKey('receipt.filename', ondelete='CASCADE'))
    receipt: Relationship[Receipt] = relationship(back_populates="products")

    quantity: MappedColumn[Quantity]
    label: MappedColumn[str]
    price: MappedColumn[Price]
    discount_indicator: MappedColumn[Optional[str]]
    discounts: Relationship[list["Discount"]] = \
        relationship(secondary=DiscountItems, back_populates="items",
                     passive_deletes=True)
    product_id: MappedColumn[Optional[int]] = \
        mapped_column(ForeignKey('product.id', ondelete='SET NULL'))
    product: Relationship[Optional[Product]] = relationship()
    position: MappedColumn[int]
    # Extracted fields from quantity
    amount: MappedColumn[float]
    unit: MappedColumn[Optional[Unit]]

    def __repr__(self) -> str:
        return (f"ProductItem(receipt={self.receipt_key!r}, "
                f"quantity='{self.quantity!s}', label={self.label!r}, "
                f"price={self.price!s}, "
                f"discount_indicator={self.discount_indicator!r}, "
                f"product={self.product_id!r})")

class Discount(Base): # pylint: disable=too-few-public-methods
    """
    Discount model for a discount action mentioned on a receipt.
    """

    __tablename__ = "receipt_discount"

    id: MappedColumn[int] = mapped_column(primary_key=True)
    receipt_key: MappedColumn[str] = \
        mapped_column(ForeignKey('receipt.filename', ondelete='CASCADE'))
    receipt: Relationship[Receipt] = relationship(back_populates="discounts")

    label: MappedColumn[str]
    price_decrease: MappedColumn[Price]
    items: Relationship[list[ProductItem]] = \
        relationship(secondary=DiscountItems, back_populates="discounts",
                     passive_deletes=True)
    position: MappedColumn[int]

    def __repr__(self) -> str:
        return (f"Discount(receipt={self.receipt_key!r}, label={self.label!r}, "
                f"price_decrease={self.price_decrease!s}, "
                f"items={[item.label for item in self.items]!r})")

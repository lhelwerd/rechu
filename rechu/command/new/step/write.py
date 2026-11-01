"""
Write step of new subcommand.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar, cast

from sqlalchemy import select
from sqlalchemy.orm import Session
from typing_extensions import override

from rechu.models.base import Origin

from ....inventory.products import Products as ProductInventory
from ....io.base import Writer
from ....io.receipt import ReceiptWriter
from ....matcher.product import ProductMatcher
from ....models import Base as ModelBase, Product, Shop
from .base import DatabaseStep, ResultMeta, ReturnToMenu

LOGGER = logging.getLogger(__name__)

T = TypeVar("T", bound=ModelBase)


@dataclass
class Write(DatabaseStep):
    """
    Final step to write the receipt to a YAML file and store in the database.
    """

    matcher: ProductMatcher
    _path: Path | None = None

    @property
    def path(self) -> Path:
        """
        Retrieve the path to which to write the receipt.
        """

        return Path(self.receipt.filename) if self._path is None else self._path

    @path.setter
    def path(self, path: Path) -> None:
        """
        Adjust the path to which to write the receipt.
        """

        self._path = path

    @override
    def run(self) -> ResultMeta:
        if not self.receipt.products:
            raise ReturnToMenu("No products added to receipt")

        self._write(ReceiptWriter(self.path, (self.receipt,)))
        with self.database as session:
            self.matcher.discounts = True
            products = self._get_products_meta(session)
            self._clear_products_meta()
            candidates = self.matcher.find_candidates(
                session, self.receipt.products, products
            )
            pairs = self.matcher.filter_duplicate_candidates(
                candidates, preferred_origin=Origin.EXTERNAL
            )
            for product, item in pairs:
                LOGGER.info("Matching %r to %r", item, product)
                item.product = product
            self._view_products_meta(
                "Products that are left out because they no longer match:",
                self._update_products_meta(session, products),
            )
            if products:
                self._delete_products_matchers(session, products)
                inventory = ProductInventory.select(session)
                updates = ProductInventory.spread(products)
                paths = inventory.merge_update(updates, update=False)
                for update in paths.get_writers():
                    self._write(update)

            shop = session.scalar(
                select(Shop).where(Shop.key == self.receipt.shop)
            )
            if shop is None:
                session.add(Shop(key=self.receipt.shop))
                session.flush()
            receipt = session.merge(self.receipt)
            LOGGER.info(
                "Receipt created: %r with %d products and %d discounts",
                receipt,
                len(receipt.products),
                len(receipt.discounts),
            )
            LOGGER.info(
                "Total discounts: %s Total price: %s",
                receipt.total_discount,
                receipt.total_price,
            )

        return {}

    def _delete_products_matchers(
        self, session: Session, products: set[Product]
    ) -> None:
        for product in products:
            if (
                cast(int | None, product.id) is not None
                and (
                    db_product := session.scalars(
                        select(Product).where(Product.id == product.id)
                    ).first()
                )
                is not None
            ):
                if not product.matchers_equals(db_product):
                    self._delete_product_matchers(session, db_product)
                for sub, db_sub in zip(
                    product.range, db_product.range, strict=False
                ):
                    if not sub.matchers_equals(db_sub):
                        self._delete_product_matchers(session, db_sub)

    def _delete_product_matchers(
        self, session: Session, product: Product
    ) -> None:
        for label in product.labels:
            session.delete(label)
        for price in product.prices:
            session.delete(price)
        for discount in product.discounts:
            session.delete(discount)

    def _write(self, writer: Writer[T]) -> None:
        writer.path.parent.mkdir(parents=True, exist_ok=True)
        writer.write()

    @property
    @override
    def description(self) -> str:
        return "Write the completed receipt and associated entries, then exit"

    @property
    @override
    def final(self) -> bool:
        return True

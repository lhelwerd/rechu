"""
Write step of new subcommand.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from typing_extensions import override

from ....database import Database
from ....inventory.products import Products as ProductInventory
from ....io.receipt import ReceiptWriter
from ....matcher.product import ProductMatcher
from ....models import Shop
from .base import ResultMeta, ReturnToMenu, Step

LOGGER = logging.getLogger(__name__)


@dataclass
class Write(Step):
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

        writer = ReceiptWriter(self.path, (self.receipt,))
        writer.write()
        with Database() as session:
            self.matcher.discounts = True
            products = self._get_products_meta(session)
            for item in self.receipt.products:
                item.product = None
            candidates = self.matcher.find_candidates(
                session, self.receipt.products, products
            )
            pairs = self.matcher.filter_duplicate_candidates(candidates)
            for product, item in pairs:
                LOGGER.info("Matching %r to %r", item, product)
                item.product = product
            if products:
                inventory = ProductInventory.select(session)
                updates = ProductInventory.spread(products)
                inventory.merge_update(updates).write()

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

    @property
    @override
    def description(self) -> str:
        return "Write the completed receipt and associated entries, then exit"

    @property
    @override
    def final(self) -> bool:
        return True

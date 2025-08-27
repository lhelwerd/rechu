"""
Write step of new subcommand.
"""

import logging
from pathlib import Path
from sqlalchemy import select
from .base import ResultMeta, ReturnToMenu, Step
from ..input import InputSource
from ....database import Database
from ....inventory.products import Products as ProductInventory
from ....io.receipt import ReceiptWriter
from ....matcher.product import ProductMatcher
from ....models import Receipt, Shop

LOGGER = logging.getLogger(__name__)

class Write(Step):
    """
    Final step to write the receipt to a YAML file and store in the database.
    """

    def __init__(self, receipt: Receipt, input_source: InputSource,
                 matcher: ProductMatcher) -> None:
        super().__init__(receipt, input_source)
        # Path should be updated based on new metadata
        self.path = Path(receipt.filename)
        self._matcher = matcher

    def run(self) -> ResultMeta:
        if not self._receipt.products:
            raise ReturnToMenu('No products added to receipt')

        writer = ReceiptWriter(self.path, (self._receipt,))
        writer.write()
        with Database() as session:
            self._matcher.discounts = True
            products = self._get_products_meta(session)
            for item in self._receipt.products:
                item.product = None
            candidates = self._matcher.find_candidates(session,
                                                       self._receipt.products,
                                                       products)
            pairs = self._matcher.filter_duplicate_candidates(candidates)
            for product, item in pairs:
                LOGGER.info('Matching %r to %r', item, product)
                item.product = product
            if products:
                inventory = ProductInventory.select(session)
                updates = ProductInventory.spread(products)
                inventory.merge_update(updates).write()

            shop = \
                session.execute(select(Shop)
                                .where(Shop.key == self._receipt.shop)).first()
            if shop is None:
                self._receipt.shop_meta = Shop(key=self._receipt.shop)
            session.merge(self._receipt)

        return {}

    @property
    def description(self) -> str:
        return "Write the completed receipt and associated entries, then exit"

    @property
    def final(self) -> bool:
        return True

"""
Read step of new subcommand.
"""

from dataclasses import dataclass
from itertools import chain
import logging
from typing import Optional, cast
from sqlalchemy import select
from sqlalchemy.orm import MappedColumn, Session
from typing_extensions import override
from .base import ResultMeta, Step
from ....database import Database
from ....inventory import Inventory
from ....inventory.products import Products as ProductInventory
from ....inventory.shops import Shops
from ....matcher.product import ProductMatcher
from ....models import Product, Shop

LOGGER = logging.getLogger(__name__)


@dataclass
class Read(Step):
    """
    Step to check if there are any new or updated product metadata entries in
    the file inventory that should be synchronized with the database inventory
    before creating and matching receipt products.
    """

    matcher: ProductMatcher

    @override
    def run(self) -> ResultMeta:
        with Database() as session:
            session.expire_on_commit = False

            # Synchronize updated shop metadata
            shops = self._update_shops(session)
            self.receipt.shop_meta = shops.find(self.receipt.shop)

            # Look for updated product metadata
            self._update_products(session, shops)

        return {}

    def _update_shops(self, session: Session) -> Inventory[Shop]:
        inventory = Shops.select(session)
        new_shops = inventory.merge_update(Shops.read()).values()
        for shops in new_shops:
            for shop in shops:
                _ = session.merge(shop)
        if new_shops:
            session.flush()
            return Shops.select(session)
        return inventory

    def _update_products(
        self, session: Session, shops: Inventory[Shop]
    ) -> None:
        database = ProductInventory.select(session)
        self.matcher.fill_map(database)

        files = ProductInventory.read()
        updates = database.merge_update(files, update=False)
        deleted = files.merge_update(database, update=False, only_new=True)
        paths = set(
            chain(
                (path.name for path in updates), (path.name for path in deleted)
            )
        )

        confirm = ""
        while paths and confirm != "y":
            LOGGER.warning("Updated products files detected: %s", paths)
            confirm = self.input.get_input("Confirm reading products (y)", str)

        for group in updates.values():
            for product in group:
                product.shop_meta = shops.find(product.shop)
                merged = session.merge(product)
                # Receive ID for new products, set in detached map product
                session.commit()
                product.id = merged.id
                _ = self.matcher.add_map(product)
        for group in deleted.values():
            for product in group:
                LOGGER.warning("Deleting %r", product)
                _ = self.matcher.discard_map(product)
                session.delete(product)

        for key in ("brand", "category", "type"):
            field = cast(MappedColumn[Optional[str]], getattr(Product, key))
            self.input.update_suggestions(
                {
                    f"{key}s": cast(
                        list[str],
                        list(
                            session.scalars(
                                select(field)
                                .distinct()
                                .filter(field.is_not(None))
                                .order_by(field)
                            )
                        ),
                    )
                }
            )

    @property
    @override
    def description(self) -> str:
        return "Check updated receipt metadata YAML files"

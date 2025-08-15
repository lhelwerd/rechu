"""
Read step of new subcommand.
"""

from itertools import chain
import logging
from sqlalchemy import select
from .base import ResultMeta, Step
from ..input import InputSource
from ....database import Database
from ....inventory.products import Products as ProductInventory
from ....matcher.product import ProductMatcher
from ....models.product import Product
from ....models.receipt import Receipt

LOGGER = logging.getLogger(__name__)

class Read(Step):
    """
    Step to check if there are any new or updated product metadata entries in
    the file inventory that should be synchronized with the database inventory
    before creating and matching receipt products.
    """

    def __init__(self, receipt: Receipt, input_source: InputSource,
                 matcher: ProductMatcher) -> None:
        super().__init__(receipt, input_source)
        self._matcher = matcher

    def run(self) -> ResultMeta:
        with Database() as session:
            session.expire_on_commit = False
            database = ProductInventory.select(session)
            self._matcher.fill_map(database)
            files = ProductInventory.read()
            updates = database.merge_update(files, update=False)
            deleted = files.merge_update(database, update=False, only_new=True)
            paths = set(chain((path.name for path in updates.keys()),
                              (path.name for path in deleted.keys())))
            confirm = ''
            while paths and confirm != 'y':
                LOGGER.warning('Updated products files detected: %s', paths)
                confirm = self._input.get_input('Confirm reading products (y)',
                                                str)

            for group in updates.values():
                for product in group:
                    self._matcher.add_map(product)
                    session.merge(product)
            for group in deleted.values():
                for product in group:
                    LOGGER.warning('Deleting %r', product)
                    self._matcher.discard_map(product)
                    session.delete(product)

            for key in ('brand', 'category', 'type'):
                field = getattr(Product, key)
                self._input.update_suggestions({
                    f'{key}s': list(session.scalars(select(field).distinct()
                                                    .filter(field.is_not(None))
                                                    .order_by(field)))
                })

        return {}

    @property
    def description(self) -> str:
        return "Check updated receipt metadata YAML files"

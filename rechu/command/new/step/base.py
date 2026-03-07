"""
Base classes and types for new subcommand steps.
"""

import logging
from abc import ABCMeta, abstractmethod
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from sqlalchemy import inspect
from sqlalchemy.orm import Session
from typing_extensions import TypedDict

from ....io.products import ProductsWriter, SharedFields
from ....models.product import Product
from ....models.receipt import ProductItem, Receipt
from ..input import InputSource


class ResultMeta(TypedDict, total=False):
    """
    Result of a step being run, indicator additional metadata to update.

    - 'receipt_path': Boolean indicating pdate the path of the receipt based on
      receipt metadata.
    """

    receipt_path: bool


Menu = dict[str, "Step"]
Pairs = tuple[tuple[Product, ProductItem], ...]

LOGGER = logging.getLogger(__name__)


class ReturnToMenu(RuntimeError):
    """
    Indication that the step is interrupted to return to a menu.
    """

    def __init__(self, msg: str = "") -> None:
        super().__init__(msg)
        self.msg: str = msg


@dataclass
class Step(metaclass=ABCMeta):
    """
    Abstract base class for a step during receipt creation.
    """

    receipt: Receipt
    input: InputSource

    @abstractmethod
    def run(self) -> ResultMeta:
        """
        Perform the step. Returns whether there is additional metadata which
        needs to be updated outside of the step.
        """

        raise NotImplementedError("Step must be implemented by subclasses")

    def _get_products_meta(self, session: Session) -> set[Product]:
        # Retrieve new/updated product metadata associated with receipt items
        return {
            item.product
            if item.product.generic is None
            else item.product.generic
            for item in self.receipt.products
            if item.product is not None
            and (
                cast(int | None, item.product.id) is None
                or item.product in session.dirty
                or inspect(item.product).modified
            )
        }

    def _clear_products_meta(self) -> None:
        for item in self.receipt.products:
            item.product = None

    def _update_products_meta(
        self, session: Session, products: set[Product]
    ) -> set[Product]:
        new_products = self._get_products_meta(session)
        unmatched = products - new_products
        products.clear()
        products.update(new_products)
        return {
            product
            for product in unmatched
            if Product(shop=product.shop).merge(product)
        }

    def _view_products_meta(
        self,
        message: str,
        products: Collection[Product],
        log_level: int | None = None,
        shared_fields: SharedFields = ("shop",),
    ) -> None:
        if products and (log_level is None or LOGGER.isEnabledFor(log_level)):
            output = (
                self.input.get_output()
                if log_level is None
                else self.input.get_error_output()
            )

            print(file=output)
            print(message, file=output)
            generic_products = set(products)

            products_writer = ProductsWriter(
                Path("products.yml"),
                [
                    product.generic if product.generic is not None else product
                    for product in products
                    if product.generic not in generic_products
                ],
                shared_fields=shared_fields,
            )
            products_writer.serialize(output)

    @property
    @abstractmethod
    def description(self) -> str:
        """
        Usage message that explains what the step does.
        """

        raise NotImplementedError("Description must be implemented by subclass")

    @property
    def final(self) -> bool:
        """
        Whether this step finalizes the receipt generation.
        """

        return False

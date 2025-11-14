"""
Base classes and types for new subcommand steps.
"""

from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from typing import cast

from sqlalchemy import inspect
from sqlalchemy.orm import Session
from typing_extensions import TypedDict

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

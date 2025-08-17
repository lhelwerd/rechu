"""
Base classes and types for new subcommand steps.
"""

from typing_extensions import TypedDict
from sqlalchemy import inspect
from sqlalchemy.orm import Session
from ..input import InputSource
from ....models.product import Product
from ....models.receipt import ProductItem, Receipt

class ResultMeta(TypedDict, total=False):
    """
    Result of a step being run, indicator additional metadata to update.

    - 'receipt_path': Boolean indicating pdate the path of the receipt based on
      receipt metadata.
    """

    receipt_path: bool

Menu = dict[str, 'Step']
Pairs = tuple[tuple[Product, ProductItem], ...]

class ReturnToMenu(RuntimeError):
    """
    Indication that the step is interrupted to return to a menu.
    """

    def __init__(self, msg: str = '') -> None:
        super().__init__(msg)
        self.msg = msg

class Step:
    """
    Abstract base class for a step during receipt creation.
    """

    def __init__(self, receipt: Receipt, input_source: InputSource) -> None:
        self._receipt = receipt
        self._input = input_source

    def run(self) -> ResultMeta:
        """
        Perform the step. Returns whether there is additional metadata which
        needs to be updated outside of the step.
        """

        raise NotImplementedError('Step must be implemented by subclasses')

    def _get_products_meta(self, session: Session) -> set[Product]:
        # Retrieve new/updated product metadata associated with receipt items
        return {
            item.product for item in self._receipt.products
            if item.product is not None and (
                item.product.id is None or item.product in session.dirty or
                inspect(item.product).modified
            )
        }

    @property
    def description(self) -> str:
        """
        Usage message that explains what the step does.
        """

        raise NotImplementedError('Description must be implemented by subclass')

    @property
    def final(self) -> bool:
        """
        Whether this step finalizes the receipt generation.
        """

        return False

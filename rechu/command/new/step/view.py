"""
View step of new subcommand.
"""

from pathlib import Path
from typing import Optional
from .base import ResultMeta, Step
from ..input import InputSource
from ....database import Database
from ....io.products import ProductsWriter
from ....io.receipt import ReceiptWriter
from ....models.product import Product
from ....models.receipt import Receipt

class View(Step):
    """
    Step to display the receipt in its YAML representation.
    """

    def __init__(self, receipt: Receipt, input_source: InputSource,
                 products: Optional[set[Product]] = None) -> None:
        super().__init__(receipt, input_source)
        self._products = products

    def run(self) -> ResultMeta:
        output = self._input.get_output()

        print(file=output)
        print("Prepared receipt:", file=output)
        writer = ReceiptWriter(Path(self._receipt.filename), (self._receipt,))
        writer.serialize(output)

        print(f"Total discount: {self._receipt.total_discount}", file=output)
        print(f"Total price: {self._receipt.total_price}", file=output)

        if self._products is not None:
            products = self._products
        else:
            with Database() as session:
                products = self._get_products_meta(session)
        if products:
            print(file=output)
            print("Prepared product metadata:", file=output)
            products_writer = ProductsWriter(Path("products.yml"), products,
                                             shared_fields=('shop',))
            products_writer.serialize(output)

        return {}

    @property
    def description(self) -> str:
        return "View receipt in its YAML format"

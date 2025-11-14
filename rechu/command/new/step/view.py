"""
View step of new subcommand.
"""

from dataclasses import dataclass
from pathlib import Path

from typing_extensions import override

from ....database import Database
from ....io.products import ProductsWriter
from ....io.receipt import ReceiptWriter
from ....models.product import Product
from .base import ResultMeta, Step


@dataclass
class View(Step):
    """
    Step to display the receipt in its YAML representation.
    """

    products: set[Product] | None = None

    @override
    def run(self) -> ResultMeta:
        output = self.input.get_output()

        print(file=output)
        print("Prepared receipt:", file=output)
        writer = ReceiptWriter(Path(self.receipt.filename), (self.receipt,))
        writer.serialize(output)

        print(f"Total discount: {self.receipt.total_discount}", file=output)
        print(f"Total price: {self.receipt.total_price}", file=output)

        if self.products is not None:
            products = self.products
        else:
            with Database() as session:
                products = self._get_products_meta(session)
        if products:
            print(file=output)
            print("Prepared product metadata:", file=output)
            products_writer = ProductsWriter(
                Path("products.yml"), products, shared_fields=("shop",)
            )
            products_writer.serialize(output)

        return {}

    @property
    @override
    def description(self) -> str:
        return "View receipt in its YAML format"

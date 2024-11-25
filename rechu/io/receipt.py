"""
Receipt file handling.
"""

from collections.abc import Iterator
from typing import IO, Union
from .base import YAMLReader
from ..models.receipt import Discount, ProductItem, Receipt

class ReceiptReader(YAMLReader[Receipt]):
    """
    Receipt file reader.
    """

    def parse(self, file: IO) -> Iterator[Receipt]:
        data = self.load(file)
        if not isinstance(data, dict):
            raise TypeError(f"File '{self._path}' does not contain a mapping")
        receipt = Receipt(filename=self._path.name, updated=self._updated,
                          date=data['date'], shop=str(data['shop']))
        receipt.products = [
            ProductItem(quantity=str(item[0]), label=item[1], price=item[2],
                        discount_indicator=item[3] if len(item) > 3 else None)
            for item in data['products']
        ]
        receipt.discounts = [
            self._discount(item, receipt.products)
            for item in data.get('bonus', [])
        ]
        yield receipt

    def _discount(self, item: list[Union[str, float]],
                  products: list[ProductItem]) -> Discount:
        discount = Discount(label=str(item[0]), price_decrease=float(item[1]))
        seen = 0
        for label in item[2:]:
            for index, product in enumerate(products[seen:]):
                if product.discount_indicator and label == product.label:
                    discount.items.append(product)
                    seen += index + 1
                    break
        return discount

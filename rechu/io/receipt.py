"""
Receipt file handling.
"""

from collections.abc import Collection, Iterator
from datetime import datetime
from pathlib import Path
from typing import IO, Optional, Union
from .base import YAMLReader, YAMLWriter
from ..models.base import Price, Quantity
from ..models.receipt import Discount, ProductItem, Receipt

_ProductItem = list[Union[str, int, Price, Quantity]]

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
            self._product(position, item)
            for position, item in enumerate(data['products'])
        ]
        receipt.discounts = [
            self._discount(position, item, receipt.products)
            for position, item in enumerate(data.get('bonus', []))
        ]
        yield receipt

    def _product(self, position: int,
                 item: list[Union[str, float]]) -> ProductItem:
        quantity = Quantity(item[0])
        discount_indicator = str(item[3]) if len(item) > 3 else None
        return ProductItem(quantity=quantity, label=str(item[1]),
                           price=Price(item[2]),
                           discount_indicator=discount_indicator,
                           position=position,
                           amount=quantity.amount, unit=quantity.unit)

    def _discount(self, position: int, item: list[Union[str, float]],
                  products: list[ProductItem]) -> Discount:
        discount = Discount(label=str(item[0]), price_decrease=Price(item[1]),
                            position=position)
        seen = 0
        for label in item[2:]:
            for index, product in enumerate(products[seen:]):
                if product.discount_indicator and label == product.label:
                    discount.items.append(product)
                    seen += index + 1
                    break
        return discount

class ReceiptWriter(YAMLWriter[Receipt]):
    """
    Receipt file writer.
    """

    def __init__(self, path: Path, models: Collection[Receipt],
                 updated: Optional[datetime] = None):
        if not models or len(models) > 1:
            raise TypeError('Can only write exactly one receipt per file')
        self._model = next(iter(models))
        if updated is None:
            updated = self._model.updated
        super().__init__(path, models, updated=updated)

    @staticmethod
    def _get_product(product: ProductItem) -> _ProductItem:
        data: _ProductItem = [product.quantity, product.label, product.price]
        if product.discount_indicator is not None:
            data.append(product.discount_indicator)
        return data

    @staticmethod
    def _get_discount(discount: Discount) -> list[Union[str, Price]]:
        data: list[Union[str, Price]] = [
            discount.label, discount.price_decrease
        ]
        data.extend([item.label for item in discount.items])
        return data

    def serialize(self, file: IO) -> None:
        data = {
            'date': self._model.date,
            'shop': self._model.shop,
            'products': [
                self._get_product(product) for product in self._model.products
            ],
            'bonus': [
                self._get_discount(bonus) for bonus in self._model.discounts
            ]
        }
        self.save(data, file)

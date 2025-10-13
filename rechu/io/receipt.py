"""
Receipt file handling.
"""

from collections.abc import Collection, Iterator
from datetime import datetime, date
from decimal import Decimal
from pathlib import Path
from typing import Optional, TextIO, Union, final
from typing_extensions import Required, TypedDict, override
from .base import YAMLReader, YAMLWriter
from ..models.base import Price, Quantity
from ..models.receipt import Discount, ProductItem, Receipt

_ProductItem = list[Union[str, float, Price, Quantity]]
_Discount = list[Union[str, Price]]


class _Receipt(TypedDict, total=False):
    date: Required[date]
    shop: Required[str]
    products: Required[list[_ProductItem]]
    bonus: list[_Discount]


@final
class ReceiptReader(YAMLReader[Receipt]):
    """
    Receipt file reader.
    """

    @override
    def parse(self, file: TextIO) -> Iterator[Receipt]:
        data = self.load(file, _Receipt)
        try:
            receipt = Receipt(
                filename=self._path.name,
                updated=self._updated,
                date=data["date"],
                shop=str(data["shop"]),
            )
            receipt.products = [
                self._product(position, item)
                for position, item in enumerate(data["products"])
            ]
            receipt.discounts = [
                self._discount(position, item, receipt.products)
                for position, item in enumerate(data.get("bonus", []))
            ]
        except KeyError as error:
            raise TypeError(
                f"Missing field in file '{self._path}': {error}"
            ) from error
        yield receipt

    def _product(self, position: int, item: _ProductItem) -> ProductItem:
        if len(item) < 3:
            raise TypeError(f"Product item has too few elements: {len(item)}")
        quantity = Quantity(item[0])
        if not isinstance(item[2], (str, float, Decimal)):
            raise TypeError(f"Price '{item[2]!r}' could not be converted")
        discount_indicator = str(item[3]) if len(item) > 3 else None
        return ProductItem(
            quantity=quantity,
            label=str(item[1]),
            price=Price(item[2]),
            discount_indicator=discount_indicator,
            position=position,
            amount=quantity.amount,
            unit=quantity.unit,
        )

    def _discount(
        self, position: int, item: _Discount, products: list[ProductItem]
    ) -> Discount:
        if len(item) < 2:
            raise TypeError(f"Discount has too few elements: {len(item)}")
        discount = Discount(
            label=str(item[0]), price_decrease=Price(item[1]), position=position
        )
        seen = 0
        for label in item[2:]:
            for index, product in enumerate(products[seen:]):
                if product.discount_indicator and label == product.label:
                    discount.items.append(product)
                    seen += index + 1
                    break
        return discount


@final
class ReceiptWriter(YAMLWriter[Receipt, _Receipt]):
    """
    Receipt file writer.
    """

    def __init__(
        self,
        path: Path,
        models: Collection[Receipt],
        updated: Optional[datetime] = None,
    ) -> None:
        if not models or len(models) > 1:
            raise TypeError("Can only write exactly one receipt per file")
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
    def _get_discount(discount: Discount) -> _Discount:
        data: list[Union[str, Price]] = [
            discount.label,
            discount.price_decrease,
        ]
        data.extend([item.label for item in discount.items])
        return data

    @override
    def serialize(self, file: TextIO) -> None:
        data: _Receipt = {
            "date": self._model.date,
            "shop": self._model.shop,
            "products": [
                self._get_product(product) for product in self._model.products
            ],
            "bonus": [
                self._get_discount(bonus) for bonus in self._model.discounts
            ],
        }
        self.save(data, file)

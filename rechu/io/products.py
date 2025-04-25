"""
Products matching metadata file handling.
"""

from typing import Iterator, IO, Union
from .base import YAMLReader, YAMLWriter
from ..models.base import Price
from ..models.product import Product, LabelMatch, PriceMatch, DiscountMatch

class ProductsReader(YAMLReader[Product]):
    """
    File reader for products metadata.
    """

    def parse(self, file: IO) -> Iterator[Product]:
        data = self.load(file)
        if not isinstance(data, dict):
            raise TypeError(f"File '{self._path}' does not contain a mapping")

        for meta in data['products']:
            product = Product(shop=data['shop'],
                              brand=meta.get('brand'),
                              description=meta.get('description'),
                              category=meta.get('category',
                                                data.get('category')),
                              type=meta.get('type', data.get('type')),
                              weight=meta.get('weight'),
                              volume=meta.get('volume'),
                              alcohol=meta.get('alcohol'),
                              sku=meta.get('sku'))

            if 'portions' in meta:
                product.portions = int(meta['portions'])
            if 'gtin' in meta:
                product.gtin = int(meta['gtin'])

            product.labels = [
                LabelMatch(name=name) for name in meta.get('labels', [])
            ]
            prices = meta.get('prices', [])
            if isinstance(prices, list):
                product.prices = [
                    PriceMatch(value=Price(price)) for price in prices
                ]
            else:
                product.prices = [
                    PriceMatch(value=Price(price), indicator=key)
                    for key, price in prices.items()
                ]
            product.discounts = [
                DiscountMatch(label=label) for label in meta.get('bonuses', [])
            ]

            yield product

_Product = dict[str, Union[str, int, list[str], list[Price], dict[str, Price]]]

class ProductsWriter(YAMLWriter[Product]):
    """
    File writer for products metadata.
    """

    @staticmethod
    def _get_prices(product: Product) -> Union[list[Price], dict[str, Price]]:
        prices: list[Price] = []
        indicator_prices: dict[str, Price] = {}

        for price in product.prices:
            if price.indicator is not None:
                indicator_prices[price.indicator] = Price(price.value)
            else:
                prices.append(Price(price.value))

        if indicator_prices:
            if prices:
                raise ValueError('Not all price matchers have indicators')
            return indicator_prices

        return prices

    def _get_product(self, product: Product, skip_fields: set[str]) -> _Product:
        data: _Product = {}
        if product.labels:
            data['labels'] = [label.name for label in product.labels]
        if product.prices:
            data['prices'] = self._get_prices(product)
        if product.discounts:
            data['bonuses'] = [discount.label for discount in product.discounts]

        fields = (
            'brand', 'description', 'category', 'type', 'portions', 'weight',
            'volume', 'alcohol', 'sku', 'gtin'
        )
        for field in fields:
            if field not in skip_fields:
                data[field] = getattr(product, field)

        return data

    def serialize(self, file: IO) -> None:
        group: dict[str, Union[str, list[_Product]]] = {}
        skip_fields = set()
        for shared in ('shop', 'category', 'type'):
            values = set(getattr(product, shared) for product in self._models)
            try:
                common = values.pop()
            except KeyError:
                common = None
            if not values and common is not None:
                group[shared] = str(common)
                skip_fields.add(shared)
            elif shared == 'shop':
                raise ValueError('Not all products are from the same shop')

        group['products'] = [
            self._get_product(product, skip_fields) for product in self._models
        ]
        self.save(group, file)

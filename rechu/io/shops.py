"""
Shops metadata file handling.
"""

from typing import IO, Iterator, Literal, get_args
from typing_extensions import TypedDict
from .base import YAMLReader, YAMLWriter
from ..models.shop import Shop, DiscountIndicator

class _Shop(TypedDict, total=False):
    """
    Serialized shop metadata.
    """

    key: str
    name: str
    website: str
    products: str
    wikidata: str
    discount_indicators: list[str]

OptionalField = Literal["name", "website", "wikidata", "products"]
OPTIONAL_FIELDS: tuple[OptionalField, ...] = get_args(OptionalField)

class ShopsReader(YAMLReader[Shop]):
    """
    File reader for shops metadata.
    """

    def parse(self, file: IO) -> Iterator[Shop]:
        data: list[_Shop] = self.load(file)
        if not isinstance(data, list):
            raise TypeError(f"File '{self._path}' does not contain an array")
        for shop in data:
            yield self._shop(shop)

    def _shop(self, data: _Shop) -> Shop:
        try:
            shop = Shop(key=data["key"],
                        name=data.get("name"),
                        website=data.get("website"),
                        products=data.get("products"),
                        wikidata=data.get("wikidata"))
            shop.discount_indicators = [
                DiscountIndicator(pattern=pattern)
                for pattern in data.get("discount_indicators", [])
            ]
            return shop
        except KeyError as error:
            raise TypeError(f"Missing field in file '{self._path}': {error}") \
                from error

class ShopsWriter(YAMLWriter[Shop]):
    """
    File writer for shops metadata.
    """

    def _shop(self, shop: Shop) -> _Shop:
        data: _Shop = {"key": shop.key}
        for field in OPTIONAL_FIELDS:
            if (value := getattr(shop, field, None)) is not None:
                data[field] = value
        if shop.discount_indicators:
            data["discount_indicators"] = [
                indicator.pattern for indicator in shop.discount_indicators
            ]
        return data

    def serialize(self, file: IO) -> None:
        data = [self._shop(shop) for shop in self._models]
        self.save(data, file)

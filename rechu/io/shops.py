"""
Shops metadata file handling.
"""

from collections.abc import Iterator
from typing import final, get_args, Literal, TextIO

from typing_extensions import override, Required, TypedDict

from ..models.shop import DiscountIndicator, Shop
from .base import YAMLReader, YAMLWriter


class _Shop(TypedDict, total=False):
    """
    Serialized shop metadata.
    """

    key: Required[str]
    name: str
    website: str
    products: str
    wikidata: str
    discount_indicators: list[str]


OptionalField = Literal["name", "website", "wikidata", "products"]
OPTIONAL_FIELDS: tuple[OptionalField, ...] = get_args(OptionalField)


@final
class ShopsReader(YAMLReader[Shop]):
    """
    File reader for shops metadata.
    """

    @override
    def parse(self, file: TextIO) -> Iterator[Shop]:
        data = self.load(file, list[_Shop])
        for shop in data:
            yield self._shop(shop)

    def _shop(self, data: _Shop) -> Shop:
        try:
            shop = Shop(
                key=data["key"],
                name=data.get("name"),
                website=data.get("website"),
                products=data.get("products"),
                wikidata=data.get("wikidata"),
            )
            shop.discount_indicators = [
                DiscountIndicator(pattern=pattern)
                for pattern in data.get("discount_indicators", [])
            ]
        except KeyError as error:
            raise TypeError(
                f"Missing field in file '{self._path}': {error}"
            ) from error

        return shop


@final
class ShopsWriter(YAMLWriter[Shop, list[_Shop]]):
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

    @override
    def serialize(self, file: TextIO) -> None:
        data = [self._shop(shop) for shop in self._models]
        self.save(data, file)

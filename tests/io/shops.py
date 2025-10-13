"""
Tests for shop metadata file handling.
"""

from io import StringIO
from itertools import zip_longest
from pathlib import Path
from typing import cast, final
import unittest
from typing_extensions import Required, TypedDict, override
import yaml
from rechu.io.shops import ShopsReader, ShopsWriter
from rechu.models.shop import Shop, DiscountIndicator


class _ExpectedShop(TypedDict, total=False):
    key: Required[str]
    name: str
    website: str
    products: str
    discount_indicators: list[str]


EXPECTED: list[_ExpectedShop] = [
    {
        "key": "id",
        "name": "iDiscount",
        "website": "https://example.com",
        "products": "{website}/products/{sku}",
        "discount_indicators": [r"[a-z]+", r"\d+%"],
    },
    {"key": "inv", "name": "Inventory"},
]


@final
class ShopsReaderTest(unittest.TestCase):
    """
    Tests for shops metadata file reader.
    """

    def test_parse(self) -> None:
        """
        Test parsing an open file and yielding shop models from it.
        """

        path = Path("samples/shops.yml")
        with path.open("r", encoding="utf-8") as file:
            index = -1
            for index, shop in enumerate(ShopsReader(path).parse(file)):
                with self.subTest(shop=index):
                    expected = EXPECTED[index]
                    self.assertEqual(shop.key, expected["key"])
                    self.assertEqual(shop.name, expected.get("name"))
                    self.assertEqual(shop.website, expected.get("website"))
                    self.assertEqual(shop.products, expected.get("products"))
                    discount_indicators = expected.get(
                        "discount_indicators", []
                    )
                    self.assertEqual(
                        len(shop.discount_indicators), len(discount_indicators)
                    )
                    for actual, pattern in zip(
                        shop.discount_indicators, discount_indicators
                    ):
                        self.assertEqual(actual.pattern, pattern)

            self.assertEqual(index, len(EXPECTED) - 1)

    def test_parse_invalid(self) -> None:
        """
        Test parsing an open file and raising type errors from it.
        """

        tests = [
            ("number.yml", "File '.*' does not contain .*list"),
            ("key.yml", "Missing field in file '.*': 'key'"),
        ]

        for filename, pattern in tests:
            with self.subTest(filename=filename):
                path = Path("samples/invalid-shops") / filename
                reader = ShopsReader(path)
                with path.open("r", encoding="utf-8") as file:
                    with self.assertRaisesRegex(TypeError, pattern):
                        self.assertIsNone(next(reader.parse(file)))


@final
class ShopsWriterTest(unittest.TestCase):
    """
    Tests for shops metadata file writer.
    """

    @override
    def setUp(self) -> None:
        self.path = Path("samples/shops.yml")
        self.models = (
            Shop(
                key="id",
                name="iDiscount",
                website="https://example.com",
                products="{website}/products/{sku}",
                discount_indicators=[
                    DiscountIndicator(pattern=r"[a-z]+"),
                    DiscountIndicator(pattern=r"\d+%"),
                ],
            ),
            Shop(key="inv", name="Inventory"),
        )

    def test_serialize(self) -> None:
        """
        Test writing a serialized variant of models to an open file.
        """

        writer = ShopsWriter(self.path, self.models)
        file = StringIO()
        writer.serialize(file)

        _ = file.seek(0)
        actual = cast(
            list[_ExpectedShop], yaml.safe_load("\n".join(file.readlines()))
        )

        self.assertEqual(len(actual), len(EXPECTED))
        for index, shop in enumerate(EXPECTED):
            with self.subTest(shop=index):
                self.assertEqual(actual[index], shop)

    def test_serialize_roundtrip(self) -> None:
        """
        Test writing a serialized variant of models to an open file and
        checking its serialization format.
        """

        writer = ShopsWriter(self.path, self.models)
        file = StringIO()
        writer.serialize(file)
        _ = file.seek(0)
        lines = file.readlines()

        # Serialization should look the same way.
        with self.path.open("r", encoding="utf-8") as original_file:
            for line, (original, new) in enumerate(
                zip_longest(original_file, lines)
            ):
                with self.subTest(line=line):
                    self.assertEqual(original, new)

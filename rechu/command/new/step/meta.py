"""
Meta step of new subcommand.
"""

import logging
import re
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import cast

from sqlalchemy import select
from sqlalchemy.sql.functions import min as min_
from typing_extensions import override

from ....io.products import (
    IDENTIFIER_FIELDS,
    OPTIONAL_FIELDS,
    ProductsReader,
    ProductsWriter,
)
from ....matcher.product import MapKey, ProductMatcher
from ....models.base import GTIN, Origin, Price, Quantity
from ....models.product import (
    DiscountMatch,
    Indicator,
    LabelMatch,
    Match,
    PriceMatch,
    Product,
)
from ....models.receipt import ProductItem, Receipt
from ..input import Input
from .base import DatabaseStep, Option as BaseOption, ResultMeta, ReturnToMenu
from .edit import Edit
from .view import View

LOGGER = logging.getLogger(__name__)


@dataclass
class MetaResult:
    """
    Result of an attempt to create or edit product metadata or portions of it.
    """

    product: Product | None = None
    loop: bool = True
    key: str | None = None
    changed: bool = False
    split_range: bool = False


@dataclass
class _Matcher:
    model: type[Match]
    key: str
    extra_key: str = ""
    input_type: type[Input] = field(default=str)
    options: str | None = None
    normalize: str = ""


@dataclass
class _Default:
    input_type: type[Input] = field(default=str)
    default: Input | None = None
    has_value: bool = False
    options: str | None = None


CONFIRM_ID: re.Pattern[str] = re.compile(r"^-?\d+$", re.ASCII)

# Product metadata match entities
MATCHERS: dict[str, _Matcher] = {
    "label": _Matcher(model=LabelMatch, key="name", options="products"),
    "price": _Matcher(
        model=PriceMatch,
        key="value",
        extra_key="indicator",
        input_type=Price,
        options="prices",
        normalize="quantity",
    ),
    "discount": _Matcher(
        model=DiscountMatch,
        key="label",
        options="discounts",
    ),
}


class Option(StrEnum):
    """
    Valid input choices to perform specific actions on product metadata.
    """

    RANGE = "range"
    SPLIT = "split"
    VIEW = "view"
    EDIT = "edit"

    END = BaseOption.END.value
    STOP = BaseOption.STOP.value
    CANCEL = BaseOption.CANCEL.value
    HELP = BaseOption.HELP.value


@dataclass
class ProductMeta(DatabaseStep):
    """
    Step to add product metadata that matches one or more products.
    """

    matcher: ProductMatcher
    more: bool = False
    products: set[Product] = field(default_factory=set[Product])
    preferred_products: set[Product] = field(default_factory=set[Product])
    preferred_origin: Origin = Origin.DATABASE
    _suggestions_loaded: bool = False

    @override
    def run(self) -> ResultMeta:
        if not self.receipt.products:
            LOGGER.info("No product items on receipt yet")
            return ResultMeta()

        # Check if there are any unmatched products on the receipt
        with self.database as session:
            self.products.update(self._get_products_meta(session))
            candidates = self.matcher.find_candidates(
                session, self.receipt.products, self.products
            )
            pairs = self.matcher.filter_duplicate_candidates(candidates)
            matched_items = {item for _, item in pairs}
            LOGGER.info(
                "%d/%d items already matched on receipt",
                len(matched_items),
                len(self.receipt.products),
            )

        result = MetaResult()
        if not self.more and len(matched_items) == len(self.receipt.products):
            while result.loop:
                result = self._add_key_value(result)
                result.changed = False
            return ResultMeta()

        result.key = None
        while (
            (result.loop or result.key == Option.CANCEL)
            and result.key != Option.STOP
            and (self.more or len(matched_items) < len(self.receipt.products))
            and any(item not in matched_items for item in self.receipt.products)
        ):
            result = self.add_product(
                initial_key=result.key, matched_items=matched_items
            )

        return ResultMeta()

    def _load_suggestions(self) -> None:
        with self.database as session:
            min_date = session.scalar(select(min_(Receipt.date)))
            if min_date is None:
                min_date = self.receipt.date
            today = date.today()
            years = range(min_date.year, today.year + 1)
            months = range(1, today.month + 1)
            self.input.update_suggestions(
                {
                    "indicators": [str(year) for year in years]
                    + [f"{today.year}-{month:0>2}" for month in months]
                    + [Indicator.MINIMUM.value, Indicator.MAXIMUM.value]
                    + [
                        str(product.unit)
                        for product in self.receipt.products
                        if product.unit is not None
                    ],
                    "prices": [
                        str(product.price) for product in self.receipt.products
                    ],
                }
            )

    def add_product(
        self,
        item: ProductItem | None = None,
        initial_key: str | None = None,
        matched_items: set[ProductItem] | None = None,
        product: Product | None = None,
    ) -> MetaResult:
        """
        Request fields for a product's metadata and add it to the database as
        well as a products YAML file. `item` is an optional product item
        from the receipt to specifically match the metadata for. `initial_key`
        is a metadata key to use for the first prompt. `matched_items` is a set
        of product items on the receipt that already have metadata. `product` is
        an existing product to start with, if any. Returns a `MetaResult` object
        indicating whether to attempt to create more product metadata (`loop`)
        and the current prompt answer (`key`).
        """

        existing = True
        if product is None:
            existing = False
            product = Product(shop=self.receipt.shop)
        initial_product = product.copy()

        self._load_suggestions()
        self.preferred_origin = Origin.DATABASE

        result = MetaResult(product=product, key=initial_key)
        matched, result.key = self._fill_product(result, item=item)
        while not matched:
            result.changed = not initial_product.equals(product)
            if result.key == Option.CANCEL:
                LOGGER.info("Discarded changes to start with fresh product")
                _ = product.replace(initial_product)
                existing = False
                result.changed = False
            elif not result.changed or result.key == Option.STOP:
                if existing:
                    _ = product.replace(initial_product)
                    LOGGER.info("Product %r was not updated", product)
                result.loop = False
                return result
            else:
                LOGGER.warning(
                    "Product %r does not match receipt item", product
                )

            result.key = self._get_key(result, item=item, ignore_key=True)
            if result.key == Option.END:
                result.loop = result.changed
                return result

            matched, result.key = self._fill_product(result, item=item)

        changed = not initial_product.equals(product)
        result.loop = item is None
        if not changed:
            # Should always be existing otherwise it would not match
            LOGGER.info("Product %r remained the same", product)
            return result

        # Track product internally (also tracked via receipt products meta)
        LOGGER.info(
            "Product %s: %r", "updated" if existing else "created", product
        )
        root = self._get_root_product(product)
        self.products.add(root)
        _ = self.matcher.add_map(root)
        if matched_items is not None:
            matched_items.update(matched)

        return result

    def _fill_product(
        self,
        result: MetaResult,
        item: ProductItem | None = None,
    ) -> tuple[set[ProductItem], str | None]:
        key = self._set_values(result, item=item)
        if (
            (product := result.product) is None
            or key in {Option.END, Option.CANCEL}
            or (item is not None and key == Option.STOP)
        ):
            # Canceled creation/merged with already-matched product
            return set(), key

        items = self.receipt.products if item is None else [item]
        matched: set[ProductItem] = set()
        with self.database as session:
            self.products.update(self._get_products_meta(session))
            matchers = set(product.range)
            matchers.add(product)
            generic = self._get_root_product(product)
            matchers.add(generic)
            matchers.update(generic.range)

            pairs = self.matcher.find_candidates(
                session, items, self.products | matchers
            )
            for meta, match in self.matcher.filter_duplicate_candidates(
                pairs, self.preferred_products, self.preferred_origin
            ):
                # Only accept the match if the current product also matches,
                # but might be overshadowed by generic or sibling range.
                if meta in matchers and self.matcher.match(product, match):
                    match.product = meta
                    matched.add(match)
                    if not match.discounts and product.discounts:
                        LOGGER.info(
                            "Matched with %r excluding discounts", match
                        )
                    else:
                        LOGGER.info("Matched with item: %r", match)
            self.products.add(self._get_root_product(product))
            self._view_products_meta(
                "Products that no longer match:",
                self._update_products_meta(session, self.products),
            )

        return matched, key

    def _set_values(
        self,
        result: MetaResult,
        item: ProductItem | None = None,
    ) -> str | None:
        while result.loop:
            result = self._add_key_value(
                result,
                item=item,
            )

        return result.key

    def _add_key_value(
        self,
        result: MetaResult,
        item: ProductItem | None = None,
    ) -> MetaResult:
        key = self._get_key(
            result,
            item=item,
        )
        product = result.product

        match key:
            case Option.RANGE | Option.SPLIT:
                return self._set_range(product, item, result.changed, key)
            case Option.VIEW:
                return self._view(product, item, result.changed)
            case Option.EDIT:
                return self._edit(product, item, result.changed)
            case Option.END:
                result.loop = False
                result.key = None
                return result
            case Option.STOP | Option.CANCEL:
                result.loop = False
                result.key = key
                return result
            case Option.HELP:
                raise ReturnToMenu
            case _:
                return self._add_metadata_key_value(result, product, item, key)

    def _add_metadata_key_value(
        self,
        result: MetaResult,
        product: Product | None,
        item: ProductItem | None,
        key: str,
    ) -> MetaResult:
        if product is None:
            LOGGER.warning("Cannot change metadata key %s without product", key)
        else:
            try:
                value = self._get_value(product, item, key)
            except KeyError:
                LOGGER.warning("Unrecognized metadata key %s", key)
                result.loop = True
                result.key = None
                return result

            self._set_key_value(product, item, key, value)

        # Check if product matchers/identifiers clash
        return self._check_duplicate(product)

    @staticmethod
    def _get_initial_range(product: Product) -> Product:
        initial = product.copy()
        setattr(initial, "id", None)
        initial.range = []
        for column in IDENTIFIER_FIELDS:
            setattr(initial, column, None)
        return initial

    def _split_range(
        self, product: Product, item: ProductItem | None
    ) -> str | None:
        key = self._get_key(
            MetaResult(product=product, split_range=True), item=item
        )
        match key:
            case Option.END | Option.CANCEL:
                return key
            case Option.HELP:
                raise ReturnToMenu
            case key if key in MATCHERS:
                key = f"{key}s"
                setattr(product, key, getattr(product, key))
                setattr(product.generic, key, [])
            case key if key in OPTIONAL_FIELDS:
                setattr(product, key, getattr(product.generic, key))
                setattr(product.generic, key, None)
            case _:
                LOGGER.warning("Unrecognized metadata key %s", key)
                return key

        return None

    def _set_range(
        self,
        product: Product | None,
        item: ProductItem | None,
        initial_changed: bool = False,
        key: str = Option.RANGE,
    ) -> MetaResult:
        result = MetaResult(
            product=product, loop=True, key=None, changed=initial_changed
        )
        if product is None:
            LOGGER.warning("Cannot add product range without a product")
            return result

        generic: Product | None = product.generic
        if generic is not None:
            LOGGER.warning("Cannot add product range to non-generic product")
            return result

        initial = self._get_initial_range(product)
        product_range = initial.copy()
        product_range.generic = product
        split_range: Product | None = None
        if key == Option.SPLIT:
            split_key: str | None = key
            while split_key not in {Option.END, Option.CANCEL}:
                split_key = self._split_range(product_range, item)
                if split_key is None:
                    split_range = product_range.copy()
                    split_range.generic = None
            if split_key == Option.CANCEL:
                result.key = split_key
                result.changed = False
                return result

        range_result = MetaResult(
            product=product_range,
            key=result.key,
            changed=split_range is not None,
        )
        initial_key = self._set_values(range_result, item=item)
        if initial_key == Option.END or initial.equals(product_range):
            product_range.generic = None
            if split_range is not None:
                _ = product.merge(split_range)
            return MetaResult(
                product=product,
                loop=True,
                key=None,
                changed=initial_changed or split_range is not None,
            )

        return MetaResult(
            product=product, loop=True, key=initial_key, changed=True
        )

    def _view(
        self,
        product: Product | None,
        item: ProductItem | None,
        initial_changed: bool = False,
    ) -> MetaResult:
        if item is not None:
            LOGGER.info("Receipt product item to match: %r", item)
        else:
            with self.database as session:
                self.products.update(self._get_products_meta(session))
            _ = View(
                receipt=self.receipt,
                input=self.input,
                database=self.database,
                products=self.products,
            ).run()

        output = self.input.get_output()
        print(file=output)

        if product is None:
            products = tuple(self.products)
            product_display = "products"
        elif (product_generic := product.generic) is not None:
            products = (product_generic,)
            product_display = "generic product"
        else:
            products = (product,)
            product_display = "product"

        print(f"Current {product_display} metadata draft:", file=output)
        ProductsWriter(
            Path("products.yml"), products, shared_fields=()
        ).serialize(output)
        if product is not None and product.generic is not None:
            LOGGER.info("Current product range metadata draft: %r", product)

        if initial_changed:
            return self._check_duplicate(product)
        return MetaResult(product=product, loop=True, key=None, changed=False)

    def _edit(
        self,
        product: Product | None,
        item: ProductItem | None,
        initial_changed: bool = False,
    ) -> MetaResult:
        products: tuple[Product, ...] = ()
        if item is None:
            products = tuple(self.products)
        product_generic = None
        if product is not None:
            if (product_generic := product.generic) is not None:
                products = (*products, product_generic)
            else:
                products = (*products, product)
        with tempfile.NamedTemporaryFile("w", suffix=".yml") as tmp_file:
            tmp_path = Path(tmp_file.name)
            writer = ProductsWriter(tmp_path, products, shared_fields=())
            writer.write()
            if item is not None:
                _ = tmp_file.write(f"# Product to match: {item!r}")

            edit = Edit(self.receipt, self.input, self.database, self.matcher)
            edit.execute_editor(tmp_file.name)

            reader = ProductsReader(tmp_path)
            try:
                self._edit_matched_products(product, tuple(reader.read()))
            except (TypeError, ValueError, IndexError):
                LOGGER.exception("Invalid or missing edited product YAML")
                return MetaResult(
                    product=product,
                    loop=True,
                    key=None,
                    changed=initial_changed,
                )

        if (
            product_generic is not None
            and product is not None
            and product.generic is None
        ):
            LOGGER.warning(
                "Range product was edited out, returning to generic product"
            )
            return MetaResult(
                product=product,
                loop=False,
                key=None,
                changed=initial_changed,
            )

        return self._check_duplicate(product)

    def _edit_matched_products(
        self,
        product: Product | None,
        new_products: tuple[Product, ...] = (),
    ) -> None:
        product_count = len(new_products) - int(product is not None)
        if product_count > 0:
            self._edit_extra_products(new_products[:product_count])

        if new_products and product is not None:
            self._replace_product(product, new_products[-1])
            self.preferred_origin = Origin.EXTERNAL

    def _edit_extra_products(self, extra_products: tuple[Product, ...]) -> None:
        products = self.products | set(extra_products)
        for extra_product in extra_products:
            _ = self.matcher.add_map(extra_product, True)

        with self.database as session:
            originals = {item: item.product for item in self.receipt.products}
            self._clear_products_meta()

            candidates = self.matcher.find_candidates(
                session,
                self.receipt.products,
                extra_products,
            )
            pairs = self.matcher.filter_duplicate_candidates(
                candidates, extra_products
            )
            for candidate, target in pairs:
                new = self._get_root_product(candidate)
                if new in products or cast(int | None, candidate.id) is None:
                    if original := originals.get(target):
                        _ = new.merge_ids(self._get_root_product(original))
                    LOGGER.info("Matching %r to %r", target, candidate)
                    target.product = candidate

            _ = self._update_products_meta(session, self.products)
            for new in extra_products:
                if new in self.products:
                    self.preferred_products.add(new)
                else:
                    LOGGER.info("Did not match %r", new)

    def _replace_product(self, product: Product, new_product: Product) -> None:
        generic: Product | None = product.generic
        if generic is not None:
            _ = new_product.merge_ids(generic)
            range_index = generic.range.index(product)
            _ = generic.replace(new_product)
            if len(generic.range) > range_index:
                _ = product.replace(generic.range[range_index])
                product.generic = generic
                generic.range[range_index:] = [product]
            else:
                # Split product was removed so go back to generic product
                _ = product.replace(generic)
        else:
            _ = new_product.merge_ids(product)
            _ = product.replace(new_product)

    def _get_key(
        self,
        result: MetaResult,
        item: ProductItem | None = None,
        ignore_key: bool = False,
    ) -> str:
        if result.key is not None and not ignore_key:
            return result.key

        options: list[Option] = []
        hidden_options: list[Option] = []
        fields = True
        product = result.product
        if result.split_range:
            skip = "empty stops splitting out for a new range meta"
        elif product is None:
            options = [Option.EDIT, Option.VIEW]
            skip = "empty ends reviewing meta"
            fields = False
        else:
            generic: Product | None = product.generic
            if generic is None:
                meta = "meta"
                options = [Option.EDIT, Option.SPLIT]
                hidden_options = [Option.RANGE]
            else:
                meta = "range meta"
                options = [Option.EDIT]

            if result.changed:
                end = "ends all" if item is None else "discards meta"
                options.append(Option.VIEW)
                skip = f"empty ends this {meta}, {Option.STOP} {end}"
            else:
                hidden_options.append(Option.VIEW)
                skip = f"empty or {Option.STOP} skips {meta}"

        if options:
            skip = f"{skip}, {', '.join(options)}"

        always_options = f"{Option.HELP} menu, {Option.CANCEL} cancel"
        prompt = f"Metadata key ({skip}, {always_options})"
        return self.get_choice(
            prompt,
            options,
            hidden_options,
            fields,
        )

    def get_choice(
        self,
        prompt: str,
        options: Sequence[Option] = (),
        hidden_options: Sequence[Option] = (),
        meta_fields: bool = True,
    ) -> str:
        """
        Obtain a key or metadata editing option by prompting a query and
        retrieving an input, possibly autocompleting the option.
        """

        matchers = [
            "label",
            "price",
            "discount",
        ]

        fields = [
            *options,
            *(matchers if meta_fields else ()),
            *(OPTIONAL_FIELDS if meta_fields else ()),
            *hidden_options,
        ]
        self.input.update_suggestions({"meta": fields})
        key = self.input.get_input(prompt, str, options="meta")
        if (
            key != ""
            and key not in fields
            and (choice := self.input.get_completion(key, 0)) is not None
        ):
            return choice

        return key

    def _get_current_default(
        self, product: Product, item: ProductItem | None, key: str
    ) -> _Default:
        default: Input | None = None
        if key in MATCHERS:
            matcher = MATCHERS[key]
            input_type = matcher.input_type
            options = matcher.options
            has_value = bool(cast(list[Match], getattr(product, f"{key}s")))
            if not has_value and item is not None:
                default = getattr(item, key, None)
            if default is not None and matcher.normalize:
                normalize = cast(Quantity, getattr(item, matcher.normalize))
                default = input_type(Quantity(default / normalize).amount)
            return _Default(
                input_type=input_type,
                default=default,
                has_value=has_value,
                options=options,
            )

        if key in OPTIONAL_FIELDS:
            return _Default(
                input_type=Product.__table__.c[key].type.python_type,
                default=None,
                has_value=getattr(product, key) is not None,
                options=f"{key}s",
            )

        raise KeyError(key)

    def _get_value(
        self, product: Product, item: ProductItem | None, key: str
    ) -> Input:
        current_default = self._get_current_default(product, item, key)
        default = current_default.default
        input_type = current_default.input_type

        match key:
            case MapKey.MAP_SKU.value:
                prompt = "Shop-specific SKU"
            case MapKey.MAP_GTIN.value:
                prompt = "GTIN-14/EAN barcode"
                input_type = GTIN
            case _:
                prompt = key.title()

        if current_default.has_value:
            default = None
            clear = "empty" if input_type is str else "negative"
            prompt = f"{prompt} ({clear} to clear field)"
        elif input_type is not str and default is None:
            prompt = f"{prompt} (negative to cancel)"

        value = self.input.get_input(
            prompt, input_type, options=current_default.options, default=default
        )
        if isinstance(value, GTIN) and not value.validate():
            LOGGER.warning("GTIN check digit incorrect: %s", value)

        return value

    def _set_key_value(
        self,
        product: Product,
        item: ProductItem | None,
        key: str,
        value: Input,
    ) -> None:
        if isinstance(value, (Price, Quantity, int)):
            empty = value < 0
        else:
            empty = value == ""

        if empty:
            self._set_empty(product, key)
        elif key in MATCHERS:
            # Handle label/price/discount differently by adding to list
            try:
                attrs = self._get_extra_key_value(product, item, key)
            except ValueError as e:
                LOGGER.warning("Could not add %s: %r", key, e)
                return

            attrs[MATCHERS[key].key] = value
            matcher = MATCHERS[key].model(**attrs)
            matchers = cast(list[Match], getattr(product, f"{key}s"))
            matchers.append(matcher)
        else:
            setattr(product, key, value)

    def _set_empty(self, product: Product, key: str) -> None:
        if key in MATCHERS:
            setattr(product, f"{key}s", [])
        else:
            setattr(product, key, None)

    def _get_extra_key_value(
        self, product: Product, item: ProductItem | None, key: str
    ) -> dict[str, Input]:
        matcher_attrs: dict[str, Input] = {}
        if extra_key := MATCHERS[key].extra_key:
            plain = any(price.indicator is None for price in product.prices)
            if not plain:
                if item is not None and item.unit is not None:
                    default = str(item.unit)
                else:
                    default = None
                indicator = self.input.get_input(
                    extra_key.title(),
                    str,
                    options=f"{extra_key}s",
                    default=default,
                )
                if indicator != "":
                    matcher_attrs[extra_key] = indicator
                elif product.prices:
                    raise ValueError("All matchers must have indicators")

        return matcher_attrs

    def _find_range_duplicate(self, product: Product) -> Product | None:
        generic: Product | None = product.generic
        if generic is None:
            return None

        # Check if there is a duplicate within the generic product
        matcher = ProductMatcher(map_keys={MapKey.MAP_SKU, MapKey.MAP_GTIN})
        matcher.clear_map()
        for similar in generic.range:
            clash = matcher.check_map(similar)
            if clash is not None and product in {similar, clash}:
                return similar if product == clash else clash
            _ = matcher.add_map(similar)

        return None

    def _find_duplicate(self, product: Product) -> Product | None:
        existing = self.matcher.check_map(product)
        if existing is None:
            if (similar := self._find_range_duplicate(product)) is not None:
                return similar

            return None

        if (
            existing == product
            or existing.generic == product
            or product.generic == existing
            or (
                cast(int | None, existing.id) is not None
                and existing.id == product.id
            )
        ):
            return None

        return existing

    def _check_duplicate(self, product: Product | None) -> MetaResult:
        if product is None:
            return MetaResult(loop=True, key=None, changed=False)

        existing = self._find_duplicate(product)
        while existing is not None:
            LOGGER.warning("Product metadata existing: %r", existing)
            merge_ids = self._generate_merge_ids(existing)
            id_text = ", ".join(merge_ids)
            if existing.generic is None:
                id_text = f"{id_text} or negative to add to range"
            prompt = f"Confirm merge by ID ({id_text}), empty to discard or key"
            confirm = self.get_choice(prompt, [], [Option.VIEW])
            if not CONFIRM_ID.match(confirm):
                LOGGER.debug("Not an ID, so empty or key: %r", confirm)
                return MetaResult(
                    product=product,
                    loop=confirm != Option.END,
                    key=confirm,
                    changed=True,
                )

            if confirm in merge_ids:
                self._merge(product, merge_ids[confirm])
                return MetaResult(
                    product=product, loop=False, key=None, changed=True
                )
            if int(confirm) < 0 and existing.generic is None:
                _ = product.merge(
                    self._get_initial_range(existing), replace=False
                )
                product.generic = existing
                return MetaResult(
                    product=product, loop=False, key=None, changed=True
                )
            LOGGER.warning("Invalid ID: %s", confirm)

        return MetaResult(product=product, loop=True, key=None, changed=True)

    @staticmethod
    def _generate_merge_ids(existing: Product) -> dict[str, Product]:
        product_id = cast(int | None, existing.id)
        merge_ids = {
            str(product_id if product_id is not None else "0"): existing
        }
        merge_ids.update(
            (
                str(index + 1 if cast(int | None, sub.id) is None else sub.id),
                sub,
            )
            for index, sub in enumerate(existing.range)
        )
        return merge_ids

    def _merge(self, product: Product, existing: Product) -> None:
        product.generic = None
        _ = product.merge(existing, replace=False)
        _ = product.merge_ids(existing)
        generic = existing.generic
        if generic is not None:
            generic.range[generic.range.index(existing)] = product
            product.generic_id = generic.id
        for item in self.receipt.products:
            if item.product == existing:
                item.product = product
        self.products.discard(existing)
        _ = self.matcher.discard_map(existing)
        self.preferred_origin = Origin.EXTERNAL

    @property
    @override
    def description(self) -> str:
        return "Create product matching metadata"

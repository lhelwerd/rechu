"""
Meta step of new subcommand.
"""

import logging
import re
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import cast

from sqlalchemy import select
from sqlalchemy.sql.functions import min as min_
from typing_extensions import Required, TypedDict, override

from ....database import Database
from ....io.products import (
    IDENTIFIER_FIELDS,
    OPTIONAL_FIELDS,
    ProductsReader,
    ProductsWriter,
)
from ....matcher.product import MapKey, ProductMatcher
from ....models.base import GTIN, Price, Quantity
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
from .base import ResultMeta, ReturnToMenu, Step
from .edit import Edit
from .view import View

LOGGER = logging.getLogger(__name__)


class _Matcher(TypedDict, total=False):
    model: Required[type[Match]]
    key: Required[str]
    extra_key: str
    input_type: type[Input]
    options: str | None
    normalize: str


_MetaResult = tuple[bool, str | None, bool]

CONFIRM_ID: re.Pattern[str] = re.compile(r"^-?\d+$", re.ASCII)

# Product metadata match entities
MATCHERS: dict[str, _Matcher] = {
    "label": {"model": LabelMatch, "key": "name", "options": "products"},
    "price": {
        "model": PriceMatch,
        "key": "value",
        "extra_key": "indicator",
        "input_type": Price,
        "options": "prices",
        "normalize": "quantity",
    },
    "discount": {
        "model": DiscountMatch,
        "key": "label",
        "options": "discounts",
    },
}


@dataclass
class ProductMeta(Step):
    """
    Step to add product metadata that matches one or more products.
    """

    matcher: ProductMatcher
    more: bool = False
    products: set[Product] = field(default_factory=set[Product])
    _suggestions_loaded: bool = False

    @override
    def run(self) -> ResultMeta:
        initial_key: str | None = None

        if not self.receipt.products:
            LOGGER.info("No product items on receipt yet")
            return {}

        # Check if there are any unmatched products on the receipt
        with Database() as session:
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

        ok = True
        while (
            (ok or initial_key == "!")
            and initial_key != "0"
            and (self.more or len(matched_items) < len(self.receipt.products))
            and any(item not in matched_items for item in self.receipt.products)
        ):
            ok, initial_key = self.add_product(
                initial_key=initial_key, matched_items=matched_items
            )

        return {}

    def _load_suggestions(self) -> None:
        with Database() as session:
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
    ) -> tuple[bool, str | None]:
        """
        Request fields for a product's metadata and add it to the database as
        well as a products YAML file. `item` is an optional product item
        from the receipt to specifically match the metadata for. `initial_key`
        is a metadata key to use for the first prompt. `matched_items` is a set
        of product items on the receipt that already have metadata. `product` is
        an existing product to start with, if any. Returns whether to no longer
        attempt to create product metadata and the current prompt answer.
        """

        existing = True
        if product is None:
            existing = False
            product = Product(shop=self.receipt.shop)
        initial_product = product.copy()

        self._load_suggestions()

        matched, initial_key = self._fill_product(
            product, item=item, initial_key=initial_key, changed=False
        )
        while not matched:
            changed = initial_product.copy().merge(product)
            if initial_key == "!":
                LOGGER.info("Discarded changes to start with fresh product")
                _ = product.replace(initial_product)
                existing = False
                changed = False
            elif not changed or initial_key == "0":
                if existing:
                    _ = product.replace(initial_product)
                    LOGGER.info("Product %r was not updated", product)
                return False, initial_key
            else:
                LOGGER.warning(
                    "Product %r does not match receipt item", product
                )

            initial_key = self._get_key(
                product, item=item, initial_changed=changed
            )
            if initial_key == "":
                return changed, initial_key

            matched, initial_key = self._fill_product(
                product, item=item, initial_key=initial_key, changed=changed
            )

        changed = initial_product.copy().merge(product)
        if not changed:
            # Should always be existing otherwise it would not match
            LOGGER.info("Product %r remained the same", product)
            return item is None, initial_key

        # Track product internally (also tracked via receipt products meta)
        LOGGER.info(
            "Product %s: %r", "updated" if existing else "created", product
        )
        self.products.add(product)
        _ = self.matcher.add_map(product)
        if matched_items is not None:
            matched_items.update(matched)

        return item is None, initial_key

    def _fill_product(
        self,
        product: Product,
        item: ProductItem | None = None,
        initial_key: str | None = None,
        changed: bool = False,
    ) -> tuple[set[ProductItem], str | None]:
        key = self._set_values(
            product, item=item, initial_key=initial_key, changed=changed
        )
        if key in {"", "!"} or (item is not None and key == "0"):
            # Canceled creation/merged with already-matched product
            return set(), key

        items = self.receipt.products if item is None else [item]
        matched: set[ProductItem] = set()
        with Database() as session:
            self.products.update(self._get_products_meta(session))
            matchers = set(product.range)
            matchers.add(product)
            if product.generic is not None:
                matchers.add(product.generic)

            pairs = self.matcher.find_candidates(
                session, items, self.products | matchers
            )
            for meta, match in self.matcher.filter_duplicate_candidates(pairs):
                if meta in matchers:
                    match.product = meta
                    matched.add(match)
                    if not match.discounts and product.discounts:
                        LOGGER.info(
                            "Matched with %r excluding discounts", match
                        )
                    else:
                        LOGGER.info("Matched with item: %r", match)

        return matched, key

    def _set_values(
        self,
        product: Product,
        item: ProductItem | None = None,
        initial_key: str | None = None,
        changed: bool = False,
    ) -> str | None:
        ok = True
        while ok:
            ok, initial_key, changed = self._add_key_value(
                product,
                item=item,
                initial_key=initial_key,
                initial_changed=changed,
            )

        return initial_key

    def _add_key_value(
        self,
        product: Product,
        item: ProductItem | None = None,
        initial_key: str | None = None,
        initial_changed: bool = False,
    ) -> _MetaResult:
        key = self._get_key(
            product,
            item=item,
            initial_key=initial_key,
            initial_changed=initial_changed,
        )

        match key:
            case "range" | "split":
                return self._set_range(product, item, initial_changed, key)
            case "view":
                return self._view(product, item, initial_changed)
            case "edit":
                return self._edit(product, item, initial_changed)
            case "" | "0" | "!":
                return False, key if key != "" else None, bool(initial_changed)
            case "?":
                raise ReturnToMenu
            case _:
                try:
                    value = self._get_value(product, item, key)
                except KeyError:
                    LOGGER.warning("Unrecognized metadata key %s", key)
                    return True, None, bool(initial_changed)

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
        key = self._get_key(product, item=item)
        match key:
            case "" | "!":
                return key
            case "?":
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
        product: Product,
        item: ProductItem | None,
        initial_changed: bool | None = None,
        key: str = "range",
    ) -> _MetaResult:
        generic: Product | None = product.generic
        if generic is not None:
            LOGGER.warning("Cannot add product range to non-generic product")
            return True, None, bool(initial_changed)

        initial = self._get_initial_range(product)
        product_range = initial.copy()
        product_range.generic = product
        split_range: Product | None = None
        if key == "split":
            split_key: str | None = key
            while split_key not in {"", "!"}:
                split_key = self._split_range(product_range, item)
                if split_key is None:
                    split_range = product_range.copy()
                    split_range.generic = None
            if split_key == "!":
                return True, split_key, False

        initial_key = self._set_values(
            product_range, item=item, changed=split_range is not None
        )
        if initial_key == "" or not initial.merge(product_range):
            product_range.generic = None
            if split_range is not None:
                _ = product.merge(split_range)
            return True, None, initial_changed or split_range is not None

        return True, initial_key, True

    def _view(
        self,
        product: Product,
        item: ProductItem | None,
        initial_changed: bool | None = None,
    ) -> _MetaResult:
        if item is not None:
            LOGGER.info("Receipt product item to match: %r", item)
        else:
            with Database() as session:
                self.products.update(self._get_products_meta(session))
            _ = View(self.receipt, self.input, products=self.products).run()

        output = self.input.get_output()
        print(file=output)

        product_generic: Product | None = product.generic
        if product_generic is None:
            products = (product,)
            product_display = "product"
        else:
            products = (product_generic,)
            product_display = "generic product"

        print(f"Current {product_display} metadata draft:", file=output)
        ProductsWriter(
            Path("products.yml"), products, shared_fields=()
        ).serialize(output)
        if product.generic is not None:
            LOGGER.info("Current product range metadata draft: %r", product)

        if initial_changed:
            return self._check_duplicate(product)
        return True, None, False

    def _edit(
        self,
        product: Product,
        item: ProductItem | None,
        initial_changed: bool | None = None,
    ) -> _MetaResult:
        products: tuple[Product, ...] = ()
        product_generic: Product | None = product.generic
        if item is None:
            products = tuple(
                existing if existing.generic is None else existing.generic
                for existing in self.products
            )
        if product_generic is None:
            products = (*products, product)
        else:
            products = (*products, product_generic)
        with tempfile.NamedTemporaryFile("w", suffix=".yml") as tmp_file:
            tmp_path = Path(tmp_file.name)
            writer = ProductsWriter(tmp_path, products, shared_fields=())
            writer.write()
            if item is not None:
                _ = tmp_file.write(f"# Product to match: {item!r}")

            edit = Edit(self.receipt, self.input, self.matcher)
            edit.execute_editor(tmp_file.name)

            reader = ProductsReader(tmp_path)
            try:
                self._edit_matched_products(product, tuple(reader.read()))
            except (TypeError, ValueError, IndexError):
                LOGGER.exception("Invalid or missing edited product YAML")
                return True, None, bool(initial_changed)

        return self._check_duplicate(product)

    def _edit_matched_products(
        self,
        product: Product,
        new_products: tuple[Product, ...] = (),
    ) -> None:
        if len(new_products) > 1:
            products = self.products | set(new_products)
            for extra_product in new_products[:-1]:
                _ = self.matcher.add_map(extra_product)

            with Database() as session:
                for item in self.receipt.products:
                    item.product = None

                candidates = self.matcher.find_candidates(
                    session, self.receipt.products, new_products[:-1]
                )
                pairs = self.matcher.filter_duplicate_candidates(candidates)
                for candidate, target in pairs:
                    if (
                        candidate in products
                        or candidate.generic in products
                        or cast(int | None, candidate.id) is None
                    ):
                        LOGGER.info("Matching %r to %r", target, candidate)
                        target.product = candidate
                self.products = self._get_products_meta(session)

        if new_products:
            generic: Product | None = product.generic
            new_product = new_products[-1]
            if generic is not None:
                setattr(new_product, "id", generic.id)
                range_index = generic.range.index(product)
                _ = generic.replace(new_product)
                _ = product.replace(generic.range[range_index])
                generic.range[range_index] = product
                _ = self.matcher.add_map(generic)
            else:
                setattr(new_product, "id", product.id)
                _ = product.replace(new_product)
                _ = self.matcher.add_map(product)

    def _get_key(
        self,
        product: Product,
        item: ProductItem | None = None,
        initial_key: str | None = None,
        initial_changed: bool | None = None,
    ) -> str:
        if initial_key is not None:
            return initial_key

        options: list[str] = []
        hidden_options: list[str] = []
        if initial_changed is None:
            skip = "empty stops splitting out for a new range meta"
        else:
            generic: Product | None = product.generic
            if generic is None:
                meta = "meta"
                options = ["edit", "split"]
                hidden_options = ["range"]
            else:
                meta = "range meta"
                options = ["edit"]

            if initial_changed:
                end = "0 ends all" if item is None else "0 discards meta"
                options.append("view")
                skip = f"empty ends this {meta}, {end}"
            else:
                hidden_options.append("view")
                skip = f"empty or 0 skips {meta}"

        if options:
            skip = f"{skip}, {', '.join(options)}"

        return self.get_choice(
            f"Metadata key ({skip}, ? menu, ! cancel)", options, hidden_options
        )

    def get_choice(
        self,
        prompt: str,
        options: Sequence[str] = (),
        hidden_options: Sequence[str] = (),
    ) -> str:
        """
        Obtain a key or metadata editing option by prompting a query and
        retrieving an input, possibly autocompleting the option.
        """

        fields = [
            *options,
            "label",
            "price",
            "discount",
            *OPTIONAL_FIELDS,
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
    ) -> tuple[type[Input], Input | None, bool, str | None]:
        default: Input | None = None
        if key in MATCHERS:
            matcher = MATCHERS[key]
            input_type = matcher.get("input_type", str)
            options = matcher.get("options")
            has_value = bool(cast(list[Match], getattr(product, f"{key}s")))
            if not has_value and item is not None:
                default = getattr(item, key, None)
            if default is not None and "normalize" in matcher:
                normalize = cast(Quantity, getattr(item, matcher["normalize"]))
                default = input_type(Quantity(default / normalize).amount)
            return input_type, default, has_value, options

        if key in OPTIONAL_FIELDS:
            input_type = Product.__table__.c[key].type.python_type
            options = f"{key}s"
            has_value = getattr(product, key) is not None
            return input_type, default, has_value, options

        raise KeyError(key)

    def _get_value(
        self, product: Product, item: ProductItem | None, key: str
    ) -> Input:
        input_type, default, has_value, options = self._get_current_default(
            product, item, key
        )

        match key:
            case MapKey.MAP_SKU.value:
                prompt = "Shop-specific SKU"
            case MapKey.MAP_GTIN.value:
                prompt = "GTIN-14/EAN barcode"
                input_type = GTIN
            case _:
                prompt = key.title()

        if has_value:
            default = None
            clear = "empty" if input_type is str else "negative"
            prompt = f"{prompt} ({clear} to clear field)"
        elif input_type is not str and default is None:
            prompt = f"{prompt} (negative to cancel)"

        return self.input.get_input(
            prompt, input_type, options=options, default=default
        )

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

            attrs[MATCHERS[key]["key"]] = value
            matcher = MATCHERS[key]["model"](**attrs)
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
        if extra_key := MATCHERS[key].get("extra_key"):
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

    def _check_duplicate(self, product: Product) -> _MetaResult:
        existing = self._find_duplicate(product)
        while existing is not None:
            LOGGER.warning("Product metadata existing: %r", existing)
            merge_ids = self._generate_merge_ids(existing)
            id_text = ", ".join(merge_ids)
            if existing.generic is None:
                id_text = f"{id_text} or negative to add to range"
            prompt = f"Confirm merge by ID ({id_text}), empty to discard or key"
            confirm = self.get_choice(prompt, [], ["view"])
            if not CONFIRM_ID.match(confirm):
                LOGGER.debug("Not an ID, so empty or key: %r", confirm)
                return confirm != "", confirm, True

            if confirm in merge_ids:
                self._merge(product, merge_ids[confirm])
                return False, None, True
            if int(confirm) < 0 and existing.generic is None:
                _ = product.merge(
                    self._get_initial_range(existing), replace=False
                )
                product.generic = existing
                return False, None, True
            LOGGER.warning("Invalid ID: %s", confirm)

        return True, None, True

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
        generic = existing.generic
        if generic is not None:
            generic.range[generic.range.index(existing)] = product
            product.generic_id = generic.id
        for item in self.receipt.products:
            if item.product == existing:
                item.product = product
        self.products.discard(existing)
        _ = self.matcher.discard_map(existing)

    @property
    @override
    def description(self) -> str:
        return "Create product matching metadata"

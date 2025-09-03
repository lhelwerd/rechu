"""
Meta step of new subcommand.
"""

from datetime import date
import logging
from pathlib import Path
import re
import tempfile
from typing import Optional
from typing_extensions import Required, TypedDict
from sqlalchemy import select
from sqlalchemy.sql.functions import min as min_
from .base import ResultMeta, ReturnToMenu, Step
from .edit import Edit
from .view import View
from ..input import Input, InputSource
from ....database import Database
from ....io.products import ProductsReader, ProductsWriter, IDENTIFIER_FIELDS, \
    OPTIONAL_FIELDS
from ....matcher.product import ProductMatcher, MapKey
from ....models.base import Base as ModelBase, GTIN, Price, Quantity
from ....models.product import Product, LabelMatch, PriceMatch, DiscountMatch
from ....models.receipt import ProductItem, Receipt

LOGGER = logging.getLogger(__name__)

class _Matcher(TypedDict, total=False):
    model: Required[type[ModelBase]]
    key: Required[str]
    extra_key: str
    input_type: type[Input]
    options: Optional[str]
    normalize: str

_MetaResult = tuple[bool, Optional[str], bool]

class ProductMeta(Step):
    """
    Step to add product metadata that matches one or more products.
    """

    CONFIRM_ID = re.compile(r"^-?\d+$", re.ASCII)

    # Product metadata match entities
    MATCHERS: dict[str, _Matcher] = {
        'label': {
            'model': LabelMatch,
            'key': 'name',
            'options': 'products'
        },
        'price': {
            'model': PriceMatch,
            'key': 'value',
            'extra_key': 'indicator',
            'input_type': Price,
            'options': 'prices',
            'normalize': 'quantity'
        },
        'discount': {
            'model': DiscountMatch,
            'key': 'label',
            'options': 'discounts'
        }
    }

    def __init__(self, receipt: Receipt, input_source: InputSource,
                 matcher: ProductMatcher, more: bool = False) -> None:
        super().__init__(receipt, input_source)
        self._matcher = matcher
        self._more = more
        self._products: set[Product] = set()

    def run(self) -> ResultMeta:
        initial_key: Optional[str] = None

        if not self._receipt.products:
            LOGGER.info('No product items on receipt yet')
            return {}

        # Check if there are any unmatched products on the receipt
        with Database() as session:
            self._products.update(self._get_products_meta(session))
            candidates = self._matcher.find_candidates(session,
                                                       self._receipt.products,
                                                       self._products)
            pairs = self._matcher.filter_duplicate_candidates(candidates)
            matched_items = {item for _, item in pairs}
            LOGGER.info('%d/%d items already matched on receipt',
                        len(matched_items), len(self._receipt.products))

            min_date = session.scalar(select(min_(Receipt.date)))
            if min_date is None:
                min_date = self._receipt.date
            years = range(min_date.year, date.today().year + 1)
            self._input.update_suggestions({
                'indicators': [str(year) for year in years] + [
                    ProductMatcher.IND_MINIMUM, ProductMatcher.IND_MAXIMUM
                ] + [
                    str(product.unit) for product in self._receipt.products
                    if product.unit is not None
                ],
                'prices': [
                    str(product.price) for product in self._receipt.products
                ]
            })

        ok = True
        while ((ok or initial_key == '!') and initial_key != '0' and
            (self._more or len(matched_items) < len(self._receipt.products)) and
            any(item not in matched_items for item in self._receipt.products)):
            ok, initial_key = self.add_product(initial_key=initial_key,
                                               matched_items=matched_items)

        return {}

    def add_product(self, item: Optional[ProductItem] = None,
                    initial_key: Optional[str] = None,
                    matched_items: Optional[set[ProductItem]] = None,
                    product: Optional[Product] = None) \
            -> tuple[bool, Optional[str]]:
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
            product = Product(shop=self._receipt.shop)
        initial_product = product.copy()

        matched, initial_key = self._fill_product(product, item=item,
                                                  initial_key=initial_key,
                                                  changed=False)
        while not matched:
            changed = initial_product.copy().merge(product)
            if not changed or initial_key in {'0', '!'}:
                if existing:
                    LOGGER.info('Product %r was not updated', product)
                return False, initial_key

            LOGGER.warning('Product %r does not match receipt item', product)
            initial_key = self._get_key(product, item=item,
                                        initial_changed=changed)
            if initial_key == '':
                return changed, initial_key

            matched, initial_key = self._fill_product(product, item=item,
                                                      initial_key=initial_key,
                                                      changed=changed)

        changed = initial_product.copy().merge(product)
        if not changed:
            # Should always be existing otherwise it would not match
            LOGGER.info('Product %r remained the same', product)
            return item is None, initial_key

        # Track product internally (also tracked via receipt products meta)
        LOGGER.info('Product %s: %r', 'updated' if existing else 'created',
                    product)
        if product.generic is None:
            self._products.add(product)
            self._matcher.add_map(product)
        if matched_items is not None:
            matched_items.update(matched)

        return item is None, initial_key

    def _fill_product(self, product: Product,
                      item: Optional[ProductItem] = None,
                      initial_key: Optional[str] = None,
                      changed: bool = False) \
            -> tuple[set[ProductItem], Optional[str]]:
        initial_key = self._set_values(product, item=item,
                                       initial_key=initial_key, changed=changed)
        if initial_key in {'', '!'}:
            # Canceled creation/merged with already-matched product
            return set(), initial_key

        items = self._receipt.products if item is None else [item]
        matched = set()
        with Database() as session:
            self._products.update(self._get_products_meta(session))
            matchers = set(product.range)
            matchers.add(product)
            if product.generic is not None:
                matchers.add(product.generic)

            pairs = self._matcher.find_candidates(session, items,
                                                  self._products | matchers)
            for meta, match in self._matcher.filter_duplicate_candidates(pairs):
                if meta in matchers:
                    match.product = meta
                    matched.add(match)
                    if not match.discounts and product.discounts:
                        LOGGER.info('Matched with %r excluding discounts',
                                    match)
                    else:
                        LOGGER.info('Matched with item: %r', match)

        return matched, initial_key

    def _set_values(self, product: Product, item: Optional[ProductItem] = None,
                    initial_key: Optional[str] = None,
                    changed: bool = False) -> Optional[str]:
        ok = True
        while ok:
            ok, initial_key, changed = \
                self._add_key_value(product, item=item, initial_key=initial_key,
                                    initial_changed=changed)

        return initial_key

    def _add_key_value(self, product: Product,
                       item: Optional[ProductItem] = None,
                       initial_key: Optional[str] = None,
                       initial_changed: bool = False) -> _MetaResult:
        key = self._get_key(product, item=item, initial_key=initial_key,
                            initial_changed=initial_changed)

        if key in {'range', 'split'}:
            return self._set_range(product, item, initial_changed, key)
        if key == 'view':
            return self._view(product, item, initial_changed)
        if key == 'edit':
            return self._edit(product, item, initial_changed)
        if key in {'', '0', '!'}:
            return False, key if key != '' else None, bool(initial_changed)
        if key == '?':
            raise ReturnToMenu

        try:
            value = self._get_value(product, item, key)
        except KeyError:
            LOGGER.warning('Unrecognized metadata key %s', key)
            return True, None, bool(initial_changed)

        self._set_key_value(product, item, key, value)

        # Check if product matchers/identifiers clash
        return self._check_duplicate(product)

    @staticmethod
    def _get_initial_range(product: Product) -> Product:
        initial = product.copy()
        initial.range = []
        for field in IDENTIFIER_FIELDS:
            setattr(initial, field, None)
        return initial

    def _split_range(self, product: Product,
                     item: Optional[ProductItem]) -> Optional[str]:
        key = self._get_key(product, item=item)
        if key in {'', '!'}:
            return key
        if key == '?':
            raise ReturnToMenu

        if key in self.MATCHERS:
            key = f'{key}s'
            setattr(product, key, getattr(product, key))
            setattr(product.generic, key, [])
        elif key in OPTIONAL_FIELDS:
            setattr(product, key, getattr(product.generic, key))
            setattr(product.generic, key, None)
        else:
            LOGGER.warning('Unrecognized metadata key %s', key)
            return key

        return None

    def _set_range(self, product: Product,
                   item: Optional[ProductItem],
                   initial_changed: Optional[bool] = None,
                   key: str = 'range') -> _MetaResult:
        if product.generic is not None:
            LOGGER.warning('Cannot add product range to non-generic product')
            return True, None, bool(initial_changed)

        initial = self._get_initial_range(product)
        product_range = initial.copy()
        product_range.generic = product
        split_range: Optional[Product] = None
        if key == 'split':
            split_key: str | None = key
            while split_key not in {'', '!'}:
                split_key = self._split_range(product_range, item)
                if split_key is None:
                    split_range = product_range.copy()
                    split_range.generic = None
            if split_key == '!':
                product_range.generic = None
                product.merge(product_range)
                return False, '', False

        initial_key = self._set_values(product_range, item=item,
                                       changed=split_range is not None)
        if initial_key == '' or not initial.merge(product_range):
            product_range.generic = None
            if split_range is not None:
                product.merge(split_range)
            return True, None, initial_changed or split_range is not None

        return True, initial_key, True

    def _view(self, product: Product, item: Optional[ProductItem],
              initial_changed: Optional[bool] = None) -> _MetaResult:
        if item is not None:
            LOGGER.info('Receipt product item to match: %r', item)
        else:
            with Database() as session:
                self._products.update(self._get_products_meta(session))
            View(self._receipt, self._input, products=self._products).run()

        output = self._input.get_output()
        print(file=output)

        if product.generic is None:
            generic = product
            product_display = "product"
        else:
            generic = product.generic
            product_display = "generic product"

        print(f'Current {product_display} metadata draft:', file=output)
        ProductsWriter(Path("products.yml"), (generic,),
                       shared_fields=()).serialize(output)
        if product.generic is not None:
            LOGGER.info('Current product range metadata draft: %r', product)

        if initial_changed:
            return self._check_duplicate(product)
        return True, None, False

    def _edit(self, product: Product, item: Optional[ProductItem],
              initial_changed: Optional[bool] = None) -> _MetaResult:
        with tempfile.NamedTemporaryFile('w', suffix='.yml') as tmp_file:
            tmp_path = Path(tmp_file.name)
            editable = product if product.generic is None else product.generic
            writer = ProductsWriter(tmp_path, (editable,), shared_fields=())
            writer.write()
            if item is not None:
                tmp_file.write(f'# Product to match: {item!r}')

            edit = Edit(self._receipt, self._input, self._matcher)
            edit.execute_editor(tmp_file.name)

            reader = ProductsReader(tmp_path)
            try:
                new_product = next(reader.read())
                if product.generic is not None:
                    range_index = editable.range.index(product)
                    editable.replace(new_product)
                    product.replace(editable.range[range_index])
                    editable.range[range_index] = product
                else:
                    product.replace(new_product)
            except (StopIteration, TypeError, ValueError, IndexError):
                LOGGER.exception('Invalid or missing edited product YAML')
                return True, None, bool(initial_changed)

        return self._check_duplicate(product)

    def _get_key(self, product: Product, item: Optional[ProductItem] = None,
                 initial_key: Optional[str] = None,
                 initial_changed: Optional[bool] = None) -> str:
        if initial_key is not None:
            return initial_key

        if initial_changed is None:
            skip = 'empty stops splitting out for a new range meta'
        else:
            if product.generic is None:
                meta = 'meta'
                options = 'edit, split'
            else:
                meta = 'range meta'
                options = 'edit'

            if initial_changed:
                end = '0 ends all' if item is None else '0 discards meta'
                skip = f'empty ends this {meta}, {end}, {options}, view'
            else:
                skip = f'empty or 0 skips {meta}, {options}'

        return self._input.get_input(f'Metadata key ({skip}, ? menu, ! cancel)',
                                     str, options='meta')

    def _get_current_default(self, product: Product,
                             item: Optional[ProductItem], key: str) \
            -> tuple[type[Input], Optional[Input], bool, Optional[str]]:
        default: Optional[Input] = None
        if key in self.MATCHERS:
            input_type = self.MATCHERS[key].get('input_type', str)
            options = self.MATCHERS[key].get('options')
            has_value = bool(getattr(product, f'{key}s'))
            if not has_value and item is not None:
                default = getattr(item, key, None)
            if default is not None and 'normalize' in self.MATCHERS[key]:
                normalize = getattr(item, self.MATCHERS[key]['normalize'])
                default = input_type(Quantity(default / normalize).amount)
            return input_type, default, has_value, options

        if key in OPTIONAL_FIELDS:
            input_type = Product.__table__.c[key].type.python_type
            options = f'{key}s'
            has_value = getattr(product, key) is not None
            return input_type, default, has_value, options

        raise KeyError(key)

    def _get_value(self, product: Product, item: Optional[ProductItem],
                   key: str) -> Input:
        prompt = key.title()
        input_type, default, has_value, options = \
            self._get_current_default(product, item, key)

        if key == MapKey.MAP_SKU.value:
            prompt = 'Shop-specific SKU'
        elif key == MapKey.MAP_GTIN.value:
            prompt = 'GTIN-14/EAN (barcode)'
            input_type = GTIN

        if has_value:
            default = None
            clear = "empty" if input_type == str else "negative"
            prompt = f'{prompt} ({clear} to clear field)'

        return self._input.get_input(prompt, input_type, options=options,
                                     default=default)

    def _set_key_value(self, product: Product, item: Optional[ProductItem],
                       key: str, value: Input) -> None:
        if isinstance(value, (Price, Quantity, int)):
            empty = value < 0
        else:
            empty = value == ""

        if empty:
            self._set_empty(product, key)
        elif key in self.MATCHERS:
            # Handle label/price/discount differently by adding to list
            try:
                attrs = self._get_extra_key_value(product, item, key)
            except ValueError as e:
                LOGGER.warning('Could not add %s: %r', key, e)
                return

            attrs[self.MATCHERS[key]['key']] = value
            matcher = self.MATCHERS[key]['model'](**attrs)
            getattr(product, f'{key}s').append(matcher)
        else:
            setattr(product, key, value)

    def _set_empty(self, product: Product, key: str) -> None:
        if key in self.MATCHERS:
            setattr(product, f'{key}s', [])
        else:
            setattr(product, key, None)

    def _get_extra_key_value(self, product: Product,
                             item: Optional[ProductItem],
                             key: str) -> dict[str, Input]:
        matcher_attrs: dict[str, Input] = {}
        if 'extra_key' in self.MATCHERS[key]:
            extra_key = self.MATCHERS[key]['extra_key']
            plain = any(price.indicator is None for price in product.prices)
            if not plain:
                if item is not None and item.unit is not None:
                    default = str(item.unit)
                else:
                    default = None
                indicator = self._input.get_input(extra_key.title(), str,
                                                  options=f'{extra_key}s',
                                                  default=default)
                if indicator != '':
                    matcher_attrs[extra_key] = indicator
                elif product.prices:
                    raise ValueError('All matchers must have indicators')

        return matcher_attrs


    def _find_duplicate(self, product: Product) -> Optional[Product]:
        existing = self._matcher.check_map(product)
        if existing is None and product.generic is not None:
            # Check if there is a duplicate within the generic product
            matcher = ProductMatcher(map_keys={MapKey.MAP_SKU, MapKey.MAP_GTIN})
            matcher.clear_map()
            for similar in product.generic.range:
                clash = matcher.check_map(similar)
                if clash is not None and product in {similar, clash}:
                    return similar if product == clash else clash
                matcher.add_map(similar)

        if existing is None or existing == product or \
            existing.generic == product or \
            (existing.id is not None and existing.id == product.id):
            return None

        return existing

    def _check_duplicate(self, product: Product) -> _MetaResult:
        existing = self._find_duplicate(product)
        while existing is not None:
            LOGGER.warning('Product metadata existing: %r', existing)
            merge_ids = self._generate_merge_ids(existing)
            id_text = ", ".join(merge_ids)
            if existing.generic is None:
                id_text = f"{id_text} or negative to add to range"
            prompt = f'Confirm merge by ID ({id_text}), empty to discard or key'
            confirm = self._input.get_input(prompt, str, options='meta')
            if not self.CONFIRM_ID.match(confirm):
                LOGGER.debug('Not an ID, so empty or key: %r', confirm)
                return confirm != '', confirm, True

            try:
                if confirm in merge_ids:
                    self._merge(product, merge_ids[confirm])
                    return False, None, True
                if int(confirm) < 0 and existing.generic is None:
                    product.merge(self._get_initial_range(existing),
                                  override=False)
                    product.generic = existing
                    return False, None, True
                LOGGER.warning('Invalid ID: %s', confirm)
            except ValueError:
                LOGGER.exception('Could not merge product metadata')

        return True, None, True

    @staticmethod
    def _generate_merge_ids(existing: Product) -> dict[str, Product]:
        merge_ids = {
            str(existing.id if existing.id is not None else "0"): existing
        }
        merge_ids.update({
            str(index + 1 if sub.id is None else sub.id): sub
            for index, sub in enumerate(existing.range)
        })
        return merge_ids

    def _merge(self, product: Product, existing: Product) -> None:
        product.generic = None
        product.merge(existing, override=False)
        generic = existing.generic
        if generic is not None:
            generic.range[generic.range.index(existing)] = product
            product.generic_id = generic.id
        for item in self._receipt.products:
            if item.product == existing:
                item.product = product
        self._products.discard(existing)
        self._matcher.discard_map(existing)

    @property
    def description(self) -> str:
        return "Create product matching metadata"

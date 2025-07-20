"""
Steps for creating a receipt in new subcommand.
"""

from datetime import date
from itertools import chain
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Optional, Union
from sqlalchemy import select
from sqlalchemy.sql.functions import count, min as min_
from typing_extensions import Required, TypedDict
from .input import Input, InputSource
from ...database import Database
from ...inventory.products import Products as ProductInventory
from ...io.products import ProductsReader, ProductsWriter, IDENTIFIER_FIELDS, \
    OPTIONAL_FIELDS
from ...io.receipt import ReceiptReader, ReceiptWriter
from ...matcher.product import ProductMatcher, MapKey
from ...models.base import Base as ModelBase, GTIN, Price, Quantity
from ...models.product import Product, LabelMatch, PriceMatch, DiscountMatch
from ...models.receipt import Discount, ProductItem, Receipt

Menu = dict[str, 'Step']
ProductsMeta = set[Product]

LOGGER = logging.getLogger(__name__)

class _Matcher(TypedDict, total=False):
    model: Required[type[ModelBase]]
    key: Required[str]
    extra_key: str
    input_type: type[Input]
    options: Optional[str]
    normalize: str

class ResultMeta(TypedDict, total=False):
    """
    Result of a step being run, indicator additional metadata to update.

    - 'receipt_path': Boolean indicating pdate the path of the receipt based on
      receipt metadata.
    """

    receipt_path: bool

_MetaResult = tuple[bool, Optional[str], bool]
_Pairs = tuple[tuple[Product, ProductItem], ...]

class ReturnToMenu(RuntimeError):
    """
    Indication that the step is interrupted to return to a menu.
    """

    def __init__(self, msg: str = '') -> None:
        super().__init__(msg)
        self.msg = msg

class Step:
    """
    Abstract base class for a step during receipt creation.
    """

    def __init__(self, receipt: Receipt, input_source: InputSource) -> None:
        self._receipt = receipt
        self._input = input_source

    def run(self) -> ResultMeta:
        """
        Perform the step. Returns whether there is additional metadata which
        needs to be updated outside of the step.
        """

        raise NotImplementedError('Step must be implemented by subclasses')

    @property
    def description(self) -> str:
        """
        Usage message that explains what the step does.
        """

        raise NotImplementedError('Description must be implemented by subclass')

    @property
    def final(self) -> bool:
        """
        Whether this step finalizes the receipt generation.
        """

        return False

class Read(Step):
    """
    Step to check if there are any new or updated product metadata entries in
    the file inventory that should be synchronized with the database inventory
    before creating and matching receipt products.
    """

    def __init__(self, receipt: Receipt, input_source: InputSource,
                 matcher: ProductMatcher) -> None:
        super().__init__(receipt, input_source)
        self._matcher = matcher

    def run(self) -> ResultMeta:
        with Database() as session:
            session.expire_on_commit = False
            database = ProductInventory.select(session)
            self._matcher.fill_map(database)
            files = ProductInventory.read()
            updates = database.merge_update(files, update=False)
            deleted = files.merge_update(database, update=False, only_new=True)
            paths = set(chain((path.name for path in updates.keys()),
                              (path.name for path in deleted.keys())))
            confirm = ''
            while paths and confirm != 'y':
                LOGGER.warning('Updated products files detected: %s', paths)
                confirm = self._input.get_input('Confirm reading products (y)',
                                                str)

            for group in updates.values():
                for product in group:
                    self._matcher.add_map(product)
                    session.merge(product)
            for group in deleted.values():
                for product in group:
                    LOGGER.warning('Deleting %r', product)
                    self._matcher.discard_map(product)
                    session.delete(product)

            for key in ('brand', 'category', 'type'):
                field = getattr(Product, key)
                self._input.update_suggestions({
                    f'{key}s': list(session.scalars(select(field).distinct()
                                                    .filter(field.is_not(None))
                                                    .order_by(field)))
                })

        return {}

    @property
    def description(self) -> str:
        return "Check updated receipt metadata YAML files"

class Products(Step):
    """
    Step to add products.
    """

    def __init__(self, receipt: Receipt, input_source: InputSource,
                 matcher: ProductMatcher, products: ProductsMeta) -> None:
        super().__init__(receipt, input_source)
        self._matcher = matcher
        self._products = products

    def run(self) -> ResultMeta:
        ok = True
        while ok:
            ok = self.add_product()

        return {}

    def add_product(self) -> bool:
        """
        Request fields for a product and add it to the receipt.
        """

        prompt = 'Quantity (empty or 0 to end products, ? to menu)'
        if self._receipt.products:
            previous = self._receipt.products[-1]
            # Check if the previous product item has a product metadata match
            # If not, we might want to create one right now
            with Database() as session:
                pairs = tuple(self._matcher.find_candidates(session, (previous,),
                                                            self._products))
                dedupe = tuple(self._matcher.filter_duplicate_candidates(pairs))
                amount = self._make_meta(previous, prompt, pairs, dedupe)
        else:
            amount = self._input.get_input(prompt, str)

        if amount in {'', '0'}:
            return False
        if amount == '?':
            raise ReturnToMenu

        try:
            quantity = Quantity(amount)
        except ValueError as error:
            LOGGER.error("Could not validate quantity: %s", error)
            return True

        label = self._input.get_input('Label', str, options='products')

        with Database() as session:
            self._input.update_suggestions({'prices': [
                str(price)
                for price in session.scalars(select(ProductItem.price, count())
                                     .where(ProductItem.label == label)
                                     .group_by(ProductItem.price)
                                     .order_by(count()))
            ]})
        price = self._input.get_input('Price', Price, options='prices')

        discount = self._input.get_input('Discount indicator', str)
        position = len(self._receipt.products)
        self._receipt.products.append(ProductItem(quantity=quantity,
                                                  label=label,
                                                  price=price,
                                                  discount_indicator=discount \
                                                      if discount != '' \
                                                      else None,
                                                  position=position,
                                                  amount=quantity.amount,
                                                  unit=quantity.unit))
        return True

    def _make_meta(self, item: ProductItem, prompt: str,
                   pairs: _Pairs, dedupe: _Pairs) -> Union[str, Quantity]:
        if dedupe and dedupe[0][0].discounts:
            LOGGER.info('Matched with %r excluding discounts', dedupe[0][0])
        elif dedupe:
            LOGGER.info('Matched with %r', dedupe[0][0])
        elif len(pairs) > 1:
            LOGGER.warning('Multiple metadata matches, ignoring for now')
        else:
            match = False
            while not match:
                meta_prompt = f'No metadata yet. Next {prompt.lower()} or key'
                key = self._input.get_input(meta_prompt, str, options='meta')
                if key in {'', '?'} or key[0].isnumeric():
                    # Quantity or other product item command
                    return key

                product = ProductMeta(self._receipt, self._input,
                                      matcher=self._matcher,
                                      products=self._products)
                match = not product.add_product(item=item, initial_key=key)[0]

        return self._input.get_input(prompt, str)

    @property
    def description(self) -> str:
        return "Add products to receipt"

class Discounts(Step):
    """
    Step to add discounts.
    """

    def __init__(self, receipt: Receipt, input_source: InputSource,
                 matcher: ProductMatcher) -> None:
        super().__init__(receipt, input_source)
        self._matcher = matcher

    def run(self) -> ResultMeta:
        ok = True
        self._matcher.discounts = True
        self._input.update_suggestions({
            'discount_items': sorted({product.label
                                      for product in self._receipt.products
                                      if product.discount_indicator})
        })
        while ok:
            ok = self.add_discount()

        return {}

    def add_discount(self) -> bool:
        """
        Request fields and items for a discount and add it to the receipt.
        """

        bonus = self._input.get_input('Discount label (empty to end discounts)',
                                     str, options='discounts')
        if bonus == '':
            return False
        if bonus == '?':
            raise ReturnToMenu
        price_decrease = self._input.get_input('Price decrease', Price)
        discount = Discount(label=bonus, price_decrease=price_decrease,
                            position=len(self._receipt.discounts))
        seen = 0
        try:
            while seen < len(self._receipt.products):
                seen = self.add_discount_item(discount, seen)
        finally:
            self._receipt.discounts.append(discount)

        return True

    def add_discount_item(self, discount: Discount, seen: int) -> int:
        """
        Request fields for a discount item.
        """

        label = self._input.get_input('Product (in order, empty to end '
                                      f'"{discount.label}", ? to menu)', str,
                                      options='discount_items')
        if label == '':
            return sys.maxsize
        if label == '?':
            raise ReturnToMenu
        discount_item: Optional[ProductItem] = None
        for index, product in enumerate(self._receipt.products[seen:]):
            if product.discount_indicator and label == product.label:
                discount_item = product
                discount.items.append(product)
                seen += index + 1
                break
        if discount_item is None:
            LOGGER.warning('No discounted product "%s" from #%d (%r)',
                           label, seen + 1, self._receipt.products[seen:])

        return seen

    @property
    def description(self) -> str:
        return "Add discounts to receipt"

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
                 matcher: ProductMatcher, products: ProductsMeta) -> None:
        super().__init__(receipt, input_source)
        self._matcher = matcher
        self._products = products

    def run(self) -> ResultMeta:
        ok = True
        initial_key: Optional[str] = None

        if not self._receipt.products:
            return {}

        # Check if there are any unmatched products on the receipt
        with Database() as session:
            candidates = self._matcher.find_candidates(session,
                                                       self._receipt.products,
                                                       self._products)
            pairs = self._matcher.filter_duplicate_candidates(candidates)
            matched_items = {item for _, item in pairs}
            LOGGER.info('%d/%d items already matched on receipt',
                        len(matched_items), len(self._receipt.products))

            if len(matched_items) == len(self._receipt.products):
                return {}

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

        while ok and initial_key != '0' and \
            any(item not in matched_items for item in self._receipt.products):
            ok, initial_key = self.add_product(initial_key=initial_key,
                                               matched_items=matched_items)

        return {}

    def add_product(self, item: Optional[ProductItem] = None,
                    initial_key: Optional[str] = None,
                    matched_items: Optional[set[ProductItem]] = None) \
            -> tuple[bool, Optional[str]]:
        """
        Request fields for a product's metadata and add it to the database as
        well as a products YAML file. `item` is an optional product item
        from the receipt to specifically match the metadata for. `initial_key`
        is a metadata key to use for the first prompt. Returns whether to no
        longer attempt to create product metadata and the current prompt answer.
        """

        product = Product(shop=self._receipt.shop)

        matched, initial_key = self._fill_product(product, item=item,
                                                  initial_key=initial_key,
                                                  changed=False)
        while not matched:
            if initial_key == '0':
                return False, initial_key

            LOGGER.warning('Product %r does not match receipt item', product)
            changed = Product(shop=self._receipt.shop).merge(product)
            if not changed:
                return False, initial_key
            initial_key = self._get_key(product, item=item,
                                        initial_changed=changed)
            if initial_key == '':
                return changed, initial_key
            if initial_key == '0':
                return False, initial_key
            if initial_key == '?':
                raise ReturnToMenu

            matched, initial_key = self._fill_product(product, item=item,
                                                      initial_key=initial_key,
                                                      changed=changed)

        # Track product for later session merge and export
        LOGGER.info('Product created: %r', product)
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
        if initial_key == '':
            # Canceled creation/merged with already-matched product
            return set(), initial_key

        items = self._receipt.products if item is None else [item]
        matched = {item for item in items if item.product == product}
        with Database() as session:
            pairs = self._matcher.find_candidates(session, items,
                                                  self._products | {product})
            match_products = {product, product.generic}.union(product.range)
            match_products.discard(None)
            for meta, match in self._matcher.filter_duplicate_candidates(pairs):
                if meta in match_products:
                    matched.add(match)
                    if not match.discounts and product.discounts:
                        LOGGER.info('Matched with %r excluding discounts',
                                    match)
                    else:
                        LOGGER.info('Matched with item: %r', match)
                        match.product = product

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
                       initial_changed: Optional[bool] = None) -> _MetaResult:
        key = self._get_key(product, item=item, initial_key=initial_key,
                            initial_changed=initial_changed)

        if key == 'range':
            return self._set_range(product, item, initial_changed)
        if key == 'view':
            return self._view(product, item, initial_changed)
        if key == 'edit':
            return self._edit(product, item, initial_changed)
        if key in {'', '0'}:
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

    def _set_range(self, product: Product,
                   item: Optional[ProductItem],
                   initial_changed: Optional[bool] = None) -> _MetaResult:
        if product.generic is not None:
            LOGGER.warning('Cannot add product range to non-generic product')
            return True, None, bool(initial_changed)

        initial = self._get_initial_range(product)
        product_range = initial.copy()
        product_range.generic = product
        initial_key = self._set_values(product_range, item=item)
        if initial_key == '' or not initial.merge(product_range):
            product_range.generic = None
            return True, None, bool(initial_changed)

        return True, initial_key, True

    def _view(self, product: Product, item: Optional[ProductItem],
              initial_changed: Optional[bool] = None) -> _MetaResult:
        if item is not None:
            LOGGER.info('Receipt product item to match: %r', item)
        else:
            View(self._receipt, self._input, products=self._products).run()

        output = self._input.get_output()
        print(file=output)
        print('Current product metadata draft:', file=output)
        ProductsWriter(Path("products.yml"), (product,),
                       shared_fields=()).serialize(output)

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

            edit = Edit(self._receipt, self._input)
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

        meta = 'meta' if product.generic is None else 'range meta'
        if initial_changed:
            end = '0 ends all' if item is None else '0 ends or discards meta'
            skip = f'empty ends this {meta}, {end}, edit, view'
        else:
            skip = f'empty or 0 skips {meta}, edit'

        return self._input.get_input(f'Metadata key ({skip}, ? menu)',
                                     str, options='meta')

    def _get_value(self, product: Product, item: Optional[ProductItem],
                   key: str) -> Input:
        prompt = key.title()
        has_value = False
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
        elif key in OPTIONAL_FIELDS:
            input_type = Product.__table__.c[key].type.python_type
            options = f'{key}s'
            has_value = getattr(product, key) is not None
        else:
            raise KeyError(key)

        if key == MapKey.MAP_SKU.value:
            prompt = 'Shop-specific SKU'
        elif key == MapKey.MAP_GTIN.value:
            prompt = 'GTIN-14/EAN (barcode)'
            input_type = GTIN

        if has_value:
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

        if key in self.MATCHERS:
            # Handle label/price/discount differently by adding to list or
            # removing if kept default with a matcher list or no item
            if empty:
                setattr(product, f'{key}s', [])
            else:
                try:
                    attrs = self._get_extra_key_value(product, item, key)
                except ValueError as e:
                    LOGGER.warning('Could not add %s: %r', key, e)
                    return

                attrs[self.MATCHERS[key]['key']] = value
                matcher = self.MATCHERS[key]['model'](**attrs)
                getattr(product, f'{key}s').append(matcher)
        else:
            setattr(product, key, value if not empty else None)

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
        if product.generic is not None and \
            (existing is None or existing.generic == product):
            matcher = ProductMatcher(map_keys={MapKey.MAP_SKU, MapKey.MAP_GTIN})
            matcher.clear_map()
            for similar in product.generic.range:
                clash = matcher.check_map(similar)
                if clash is not None and product in {similar, clash}:
                    return similar if product == clash else clash
                matcher.add_map(similar)

        return existing

    def _check_duplicate(self, product: Product) -> _MetaResult:
        existing = self._find_duplicate(product)
        while existing is not None and existing.generic != product:
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

class View(Step):
    """
    Step to display the receipt in its YAML representation.
    """

    def __init__(self, receipt: Receipt, input_source: InputSource,
                 products: Optional[ProductsMeta] = None) -> None:
        super().__init__(receipt, input_source)
        self._products = products

    def run(self) -> ResultMeta:
        output = self._input.get_output()

        print(file=output)
        print("Prepared receipt:", file=output)
        writer = ReceiptWriter(Path(self._receipt.filename), (self._receipt,))
        writer.serialize(output)

        if self._products:
            print(file=output)
            print("Prepared product metadata:", file=output)
            products = ProductsWriter(Path("products.yml"), self._products,
                                      shared_fields=('shop',))
            products.serialize(output)

        return {}

    @property
    def description(self) -> str:
        return "View receipt in its YAML format"

class Edit(Step):
    """
    Step to edit the receipt in its YAML representation via a temporary file.
    """

    def __init__(self, receipt: Receipt, input_source: InputSource,
                 editor: Optional[str] = None) -> None:
        super().__init__(receipt, input_source)
        self.editor = editor

    def run(self) -> ResultMeta:
        with tempfile.NamedTemporaryFile('w', suffix='.yml') as tmp_file:
            tmp_path = Path(tmp_file.name)
            writer = ReceiptWriter(tmp_path, (self._receipt,))
            writer.write()

            self.execute_editor(tmp_file.name)

            reader = ReceiptReader(tmp_path, updated=self._receipt.updated)
            try:
                receipt = next(reader.read())
                # Replace receipt
                update_path = self._receipt.date != receipt.date or \
                    self._receipt.shop != receipt.shop
                self._receipt.date = receipt.date
                self._receipt.shop = receipt.shop
                self._receipt.products = receipt.products
                self._receipt.discounts = receipt.discounts
                return {'receipt_path': update_path}
            except (StopIteration, TypeError, ValueError) as error:
                raise ReturnToMenu('Invalid or missing edited receipt YAML') \
                    from error

    def execute_editor(self, filename: str) -> None:
        """
        Open an editor to edit the provided filename.
        """

        # Find editor which can be found in the PATH
        editors = [
            self.editor, os.getenv('VISUAL'), os.getenv('EDITOR'),
            'editor', 'vim'
        ]
        for editor in editors:
            if editor is not None and \
                shutil.which(editor.split(' ', 1)[0]) is not None:
                break
        else:
            raise ReturnToMenu('No editor executable found')

        # Spawn selected editor
        try:
            subprocess.run(editor.split(' ') + [filename], check=True)
        except subprocess.CalledProcessError as exit_status:
            raise ReturnToMenu('Editor returned non-zero exit status') \
                from exit_status

    @property
    def description(self) -> str:
        return "Edit the current receipt via its YAML format"

class Write(Step):
    """
    Final step to write the receipt to a YAML file and store in the database.
    """

    def __init__(self, receipt: Receipt, input_source: InputSource,
                 matcher: ProductMatcher, products: ProductsMeta) -> None:
        super().__init__(receipt, input_source)
        # Path should be updated based on new metadata
        self.path = Path(receipt.filename)
        self._products = products
        self._matcher = matcher

    def run(self) -> ResultMeta:
        if not self._receipt.products:
            raise ReturnToMenu('No products added to receipt')

        writer = ReceiptWriter(self.path, (self._receipt,))
        writer.write()
        with Database() as session:
            self._matcher.discounts = True
            candidates = self._matcher.find_candidates(session,
                                                       self._receipt.products,
                                                       self._products)
            pairs = self._matcher.filter_duplicate_candidates(candidates)
            for product, item in pairs:
                LOGGER.info('Matching %r to %r', item, product)
                item.product = product
            if self._products:
                inventory = ProductInventory.select(session)
                updates = ProductInventory.spread(self._products)
                LOGGER.debug('%r %r', updates, self._products)
                inventory.merge_update(updates).write()

            session.merge(self._receipt)

        return {}

    @property
    def description(self) -> str:
        if self._products:
            return "Write completed receipt and product metadata, then exit"
        return "Write the completed receipt and exit"

    @property
    def final(self) -> bool:
        return True

class Quit(Step):
    """
    Step to exit the receipt creation menu.
    """

    def run(self) -> ResultMeta:
        LOGGER.warning('Discarding entire receipt')
        return {}

    @property
    def description(self) -> str:
        return "Exit the receipt creation menu without writing"

    @property
    def final(self) -> bool:
        return True

class Help(Step):
    """
    Step to display help for steps that are usable from the menu.
    """

    def __init__(self, receipt: Receipt, input_source: InputSource):
        super().__init__(receipt, input_source)
        self.menu: Menu = {}

    @property
    def description(self) -> str:
        return "View this usage help message"

    def run(self) -> ResultMeta:
        output = self._input.get_output()
        choice_length = len(max(self.menu, key=len))
        for choice, step in self.menu.items():
            print(f"{choice: <{choice_length}} {step.description}", file=output)

        print("Initial characters match the first option with that prefix.",
              file=output)
        return {}

"""
Subcommand to create a new receipt YAML file and import it.
"""

from datetime import datetime, date, time
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Optional, Sequence, TextIO, TypeVar, Union, TYPE_CHECKING
try:
    import readline
except ImportError:
    if not TYPE_CHECKING:
        readline = None
import dateutil.parser
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.sql.functions import count, min as min_
from typing_extensions import Required, TypedDict
from .base import Base
from ..database import Database
from ..io.products import ProductsWriter
from ..io.receipt import ReceiptReader, ReceiptWriter
from ..matcher import ProductMatcher
from ..models.base import Base as ModelBase, GTIN, Price
from ..models.product import Product, LabelMatch, PriceMatch, DiscountMatch
from ..models.receipt import Discount, ProductItem, Receipt
from ..models.shop import Shop

_Input = Union[str, int, float]
Input = TypeVar('Input', bound=_Input)
_Cast = Union[_Input, Price]
_Menu = dict[str, 'Step']
_ProductsMeta = set[Product]

class _Matcher(TypedDict, total=False):
    model: Required[type[ModelBase]]
    key: Required[str]
    extra_key: str
    input_type: type[_Input]
    type_cast: type[_Cast]
    options: Optional[str]

class _ResultMeta(TypedDict, total=False):
    receipt_path: bool
    product_meta: _ProductsMeta

class InputSource:
    """
    Abstract base class for a typed input source.
    """

    def get_input(self, name: str, input_type: type[Input],
                  options: Optional[str] = None) -> Input:
        """
        Retrieve an input cast to a certain type (string, integer or float).
        Optionally, the input source provides suggestions from a predefined
        completion source defined by the `options` name.
        """

        raise NotImplementedError('Input must be retrieved by subclasses')

    def get_date(self) -> datetime:
        """
        Retrieve a date input.
        """

        raise NotImplementedError('Date input be retrieved by subclasses')

    def get_output(self) -> TextIO:
        """
        Retrieve an output stream to write content to.
        """

        raise NotImplementedError('Output must be implemented by subclasses')

    def update_suggestions(self, suggestions: dict[str, list[str]]) -> None:
        """
        Include additional suggestion completion sources.
        """

    def get_completion(self, text: str, state: int) -> Optional[str]:
        """
        Retrieve a completion option for the current suggestions and text state.
        The `text` is a partial input that matches some part of the suggestions
        and `state` indicates the position of the suggestion in the sorted
        list of matching suggestions to choose.

        If there is no match found or if the input source does not support
        completion suggestions, then `None` is returned.
        """

        raise NotImplementedError('Should be implemented by subclasses')

class Prompt(InputSource):
    """
    Standard input prompt.
    """

    def __init__(self) -> None:
        self._suggestions: dict[str, list[str]] = {}
        self._options: list[str] = []
        self._matches: list[str] = []
        self.register_readline()

    def get_input(self, name: str, input_type: type[Input],
                  options: Optional[str] = None) -> Input:
        """
        Retrieve an input cast to a certain type (string, integer or float).
        """

        if options is not None and options in self._suggestions:
            self._options = self._suggestions[options]
        else:
            self._options = []

        value: Optional[_Input] = None
        while not isinstance(value, input_type):
            try:
                value = input_type(input(f'{name}: '))
            except ValueError as e:
                logging.warning('Invalid %s: %s', input_type.__name__, e)
        return value

    def get_date(self) -> datetime:
        date_value: Optional[datetime] = None
        while not isinstance(date_value, datetime):
            try:
                date_value = dateutil.parser.parse(self.get_input('Date', str))
            except ValueError as e:
                logging.warning('Invalid timestamp: %s', e)
        return date_value

    def get_output(self) -> TextIO:
        return sys.stdout

    def update_suggestions(self, suggestions: dict[str, list[str]]) -> None:
        self._suggestions.update(suggestions)

    def get_completion(self, text: str, state: int) -> Optional[str]:
        if state == 0:
            if text == '':
                self._matches = self._options
            else:
                self._matches = [
                    option for option in self._options
                    if option.startswith(text)
                ]
        try:
            return self._matches[state]
        except IndexError:
            return None

    def display_matches(self, substitution: str, matches: Sequence[str],
                        longest_match_length: int) -> None:
        """
        Write a display of matches to the standard output compatible with
        readline buffers.
        """

        line_buffer = readline.get_line_buffer()
        output = self.get_output()
        print(file=output)

        length = int(max(map(len, matches), default=longest_match_length) * 1.2)
        template = f"{{:<{length}}}"
        buffer = ""
        for match in matches:
            display = template.format(match[len(substitution):])
            if buffer != "" and len(buffer + display) > 80:
                print(buffer, file=output)
                buffer = ""
            buffer += display

        if buffer:
            print(buffer, file=output)

        print("> ", end="", file=output)
        print(line_buffer, end="", file=output)
        output.flush()

    def register_readline(self) -> None:
        """
        Register completion method to the `readline` module.
        """

        if readline is not None: # pragma: no cover
            readline.set_completer_delims('\t\n;')
            readline.set_completer(self.get_completion)
            readline.set_completion_display_matches_hook(self.display_matches)
            readline.parse_and_bind('tab: complete')
            readline.parse_and_bind('bind ^I rl_complete')

class ReturnToMenu(RuntimeError):
    """
    Indication that the step is interrupted to return to a menu.
    """

class Step:
    """
    Abstract base class for a step during receipt creation.
    """

    def __init__(self, receipt: Receipt, input_source: InputSource) -> None:
        self._receipt = receipt
        self._input = input_source

    def run(self) -> _ResultMeta:
        """
        Perform the step. Returns whether there is additional metadata which
        needs to be updated outside of the step, including possibly:
        - 'receipt_path': Boolean indicating pdate the path of the receipt 
          based on receipt metadata.
        - 'product_meta': Set of newly created products or merged products
          which should be merged with the database during a write.
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

class Products(Step):
    """
    Step to add products.
    """

    def __init__(self, receipt: Receipt, input_source: InputSource,
                 matcher: Optional[ProductMatcher] = None) -> None:
        super().__init__(receipt, input_source)
        self._matcher = matcher
        self._products: _ProductsMeta = set()

    def run(self) -> _ResultMeta:
        ok = True
        while ok:
            ok = self.add_product()

        return {'product_meta': self._products}

    def add_product(self) -> bool:
        """
        Request fields for a product and add it to the receipt.
        """

        prompt = 'Quantity (empty or 0 to end products, ? to menu)'
        if self._receipt.products:
            previous = self._receipt.products[-1]
            match = Match(self._receipt, self._input, matcher=self._matcher,
                          items=(previous,))
            match.run()
            quantity = self._make_meta(previous, prompt)
        else:
            quantity = self._input.get_input(prompt, str)

        if quantity in {'', '0'}:
            return False
        if quantity == '?':
            raise ReturnToMenu

        label = self._input.get_input('Label', str, options='products')

        with Database() as session:
            self._input.update_suggestions({'prices': [
                str(price)
                for price in session.scalars(select(ProductItem.price, count())
                                     .where(ProductItem.label == label)
                                     .group_by(ProductItem.price)
                                     .order_by(count()))
            ]})
        price = self._input.get_input('Price', float, options='prices')

        discount = self._input.get_input('Discount indicator', str)
        position = len(self._receipt.products)
        self._receipt.products.append(ProductItem(quantity=quantity,
                                                  label=label,
                                                  price=price,
                                                  discount_indicator=discount \
                                                      if discount != '' \
                                                      else None,
                                                  position=position))
        return True

    def _make_meta(self, item: ProductItem, prompt: str) -> str:
        ok = item.product is None
        while ok:
            meta_prompt = f'No metadata yet. Next {prompt.lower()} or key'
            key = self._input.get_input(meta_prompt, str, options='meta')
            if key in {'', '?'} or key[0].isnumeric():
                # Quantity or other product item command
                return key

            product = ProductMeta(self._receipt, self._input,
                                  matcher=self._matcher, item=item)
            ok = product.add_product(initial_key=key)[0]
            self._products.update(product.products)

        return self._input.get_input(prompt, str)

    @property
    def description(self) -> str:
        return "Add products to receipt"

class Discounts(Step):
    """
    Step to add discounts.
    """

    def run(self) -> _ResultMeta:
        ok = True
        self._input.update_suggestions({
            'discount_items': sorted(set(product.label
                                         for product in self._receipt.products
                                         if product.discount_indicator))
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
        price_decrease = self._input.get_input('Price decrease', float)
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
            logging.warning('No discounted product "%s" from #%d (%r)',
                            label, seen + 1, self._receipt.products[seen:])

        return seen

    @property
    def description(self) -> str:
        return "Add discounts to receipt"

class Match(Step):
    """
    Step to match the items in the receipt to product metadata.
    """

    def __init__(self, receipt: Receipt, input_source: InputSource,
                 matcher: Optional[ProductMatcher] = None,
                 items: Optional[Sequence[ProductItem]] = None) -> None:
        super().__init__(receipt, input_source)
        if matcher is not None:
            self._matcher = matcher
        else:
            self._matcher = ProductMatcher()
        if items is not None:
            self.items = items
        else:
            self.items = self._receipt.products

    def run(self) -> _ResultMeta:
        with Database() as session:
            candidates = self._matcher.find_candidates(session, self.items)
            pairs = self._matcher.filter_duplicate_candidates(candidates)
            for product, item in pairs:
                logging.info('Matching %r to %r', item, product)
                item.product = product

        return {}

    @property
    def description(self) -> str:
        return "Match receipt products to metadata"

class ProductMeta(Step):
    """
    Step to add product metadata that matches one or more products.
    """

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
            'input_type': float,
            'type_cast': Price,
            'options': 'prices'
        },
        'discount': {
            'model': DiscountMatch,
            'key': 'label',
            'options': 'discounts'
        }
    }

    def __init__(self, receipt: Receipt, input_source: InputSource,
                 matcher: Optional[ProductMatcher] = None,
                 item: Optional[ProductItem] = None) -> None:
        super().__init__(receipt, input_source)
        if matcher is not None:
            self._matcher = matcher
        else:
            logging.warning('No product matcher given; making one with no map')
            self._matcher = ProductMatcher()
        self._item = item
        self._products: _ProductsMeta = set()

    @property
    def products(self) -> _ProductsMeta:
        """
        Retrieve a set of newly created products or merged products to be merged
        with the database during a write.
        """

        return self._products

    def run(self) -> _ResultMeta:
        self._input.update_suggestions({
            'prices': [str(product.price) for product in self._receipt.products]
        })

        ok = True
        initial_key: Optional[str] = None
        while ok and initial_key != '0':
            ok, initial_key = self.add_product(initial_key)

        return {'product_meta': self._products}

    def add_product(self, initial_key: Optional[str] = None) \
            -> tuple[bool, Optional[str]]:
        """
        Request fields for a product's metadata and add it to the database as
        well as a products YAML file.
        """

        product = Product(shop=self._receipt.shop)

        matched = False
        while not matched:
            matched, initial_key = self._fill_product(product, initial_key)
            if not matched:
                if initial_key == '0':
                    return False, initial_key
                logging.warning('Product does not match receipt item')
                skip = 'ends all' if self._item is None else 'skips meta'
                prompt = f'Key (empty to discard this meta, 0 {skip}, ? menu)'
                initial_key = self._input.get_input(prompt, str, options='meta')
                if initial_key == '':
                    return True, initial_key
                if initial_key == '0':
                    return False, initial_key
                if initial_key == '?':
                    raise ReturnToMenu

        # Track product for later session merge and export
        self._products.add(product)
        self._matcher.add_map(product)

        return self._item is None, initial_key

    def _fill_product(self, product: Product,
                      initial_key: Optional[str]) -> tuple[bool, Optional[str]]:
        ok = True
        while ok:
            ok, initial_key = self._add_key_value(product, initial_key)

        items = self._receipt.products if self._item is None else [self._item]
        matched = False
        for item in items:
            if self._matcher.match(product, item):
                matched = True
                item.product = product

        return matched, initial_key

    def _add_key_value(self, product: Product, initial_key: Optional[str]) \
            -> tuple[bool, Optional[str]]:
        # Request key/value (skip key first time if initial_key)
        if initial_key is not None:
            key = initial_key
            initial_key = None
        else:
            prompt = 'Key (empty ends this product meta, 0 ends all, ? menu)'
            key = self._input.get_input(prompt, str, options='meta')

        if key == '':
            return False, None
        if key == '0':
            return False, key
        if key == '?':
            raise ReturnToMenu

        columns = Product.__table__.c
        if (key not in columns or not columns[key].nullable) and \
            key not in self.MATCHERS:
            logging.warning('Unrecognized metadata key %s', key)
            return True, None

        prompt = key.title()
        if key in self.MATCHERS:
            input_type = self.MATCHERS[key].get('input_type', str)
            options = self.MATCHERS[key].get('options')
        else:
            input_type = columns[key].type.python_type
            options = None

        if key == ProductMatcher.MAP_SKU:
            prompt = 'Shop-specific SKU'
        elif key == ProductMatcher.MAP_GTIN:
            prompt = 'GTIN-14/EAN (barcode)'
            input_type = GTIN
        value: _Cast = self._input.get_input(prompt, input_type,
                                             options=options)
        self._set_key_value(product, key, value, input_type)

        # Check if product matchers/identifiers clash
        return self._check_duplicate(product)

    def _set_key_value(self, product: Product, key: str, value: _Cast,
                       input_type: type[_Input]) -> None:
        if key in self.MATCHERS:
            # Handle label/price/bonus differently by adding to list
            matcher_attrs: dict[str, _Cast] = {}
            value = self.MATCHERS[key].get('type_cast', input_type)(value)
            if 'extra_key' in self.MATCHERS[key]:
                extra_key = self.MATCHERS[key]['extra_key']
                indicator = self._input.get_input(extra_key.title(), str,
                                                  options=f'{extra_key}s')
                if indicator != '':
                    matcher_attrs[extra_key] = indicator
            matcher_attrs[self.MATCHERS[key]['key']] = value
            matcher = self.MATCHERS[key]['model'](**matcher_attrs)
            getattr(product, f'{key}s').append(matcher)
        else:
            setattr(product, key, value)

    def _check_duplicate(self, product: Product) -> tuple[bool, Optional[str]]:
        existing = self._matcher.check_map(product)
        while existing is not None:
            logging.warning('Product metadata existing: %r', existing)
            prompt = 'Confirm merge by ID, key or empty to cancel metadata'
            confirm = self._input.get_input(prompt, str, options='meta')
            if confirm.isnumeric():
                if int(confirm) == existing.id:
                    product.merge(existing)
                    return False, None
                logging.warning('Invalid ID: %s', confirm)

            return True, confirm

        return True, None

    @property
    def description(self) -> str:
        return "Create product matching metadata"

class View(Step):
    """
    Step to display the receipt in its YAML representation.
    """

    def __init__(self, receipt: Receipt, input_source: InputSource,
                 products: Optional[_ProductsMeta] = None) -> None:
        super().__init__(receipt, input_source)
        self._products = products

    def run(self) -> _ResultMeta:
        output = self._input.get_output()

        writer = ReceiptWriter(Path(self._receipt.filename), (self._receipt,))
        writer.serialize(output)

        if self._products:
            products = ProductsWriter(Path("products.yml"), self._products)
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

    def run(self) -> _ResultMeta:
        with tempfile.NamedTemporaryFile(suffix='.yml') as tmp_file:
            tmp_path = Path(tmp_file.name)
            writer = ReceiptWriter(tmp_path, (self._receipt,))
            writer.write()

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
                subprocess.run(editor.split(' ') + [tmp_file.name], check=True)
            except subprocess.CalledProcessError as exit_status:
                raise ReturnToMenu('Editor returned non-zero exit status') \
                    from exit_status

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
            except (StopIteration, TypeError) as error:
                raise ReturnToMenu('Invalid or missing YAML from edited file') \
                    from error

    @property
    def description(self) -> str:
        return "Edit the current receipt via its YAML format"

class Write(Step):
    """
    Final step to write the receipt to a YAML file and store in the database.
    """

    def __init__(self, receipt: Receipt, input_source: InputSource,
                 confirm: bool = False,
                 products: Optional[_ProductsMeta] = None) -> None:
        super().__init__(receipt, input_source)
        # Path should be updated based on new metadata
        self.path = Path(receipt.filename)
        self._confirm = confirm
        self._products = products

    def run(self) -> _ResultMeta:
        if not self._receipt.products:
            raise ReturnToMenu('No products added to receipt')

        if self._confirm and \
            self._input.get_input('Confirm write (y)', str) != 'y':
            raise ReturnToMenu('Confirmation canceled')

        writer = ReceiptWriter(self.path, (self._receipt,))
        writer.write()
        with Database() as session:
            session.add(self._receipt)
            if self._products is not None:
                for product in self._products:
                    session.merge(product)

        # Export products YAML files based on the files the products belong to

        return {}

    @property
    def description(self) -> str:
        confirm = " after confirmation" if self._confirm else ""
        return f"Write the completed receipt{confirm} and exit"

    @property
    def final(self) -> bool:
        return True

class Quit(Step):
    """
    Step to exit the receipt creation menu.
    """

    def run(self) -> _ResultMeta:
        logging.info('Discarding entire receipt')
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
        self.menu: _Menu = {}

    @property
    def description(self) -> str:
        return "View this usage help message"

    def run(self) -> _ResultMeta:
        output = self._input.get_output()
        choice_length = len(max(self.menu, key=len))
        for choice, step in self.menu.items():
            print(f"{choice: <{choice_length}} {step.description}", file=output)

        print("Initial characters match the first option with that prefix.",
              file=output)
        return {}

@Base.register("new")
class New(Base):
    """
    Create a YAML file for a receipt and import it to the database.
    """

    subparser_keywords = {
        'help': 'Create receipt file and import',
        'description': 'Interactively fill in a YAML file for a receipt and '
                       'import it to the database.'
    }
    subparser_arguments = [
        (('-c', '--confirm'), {
            'action': 'store_true',
            'default': False,
            'help': 'Confirm before creating the receipt file and entry'
        })
    ]

    def __init__(self) -> None:
        super().__init__()
        self.confirm = False

    def _get_menu_step(self, menu: _Menu, input_source: InputSource) -> Step:
        choice: Optional[str] = None
        while choice not in menu:
            choice = input_source.get_input('Menu (help or ? for usage)', str,
                                            options='menu')
            if choice not in menu:
                # Autocomplete
                choice = input_source.get_completion(choice, 0)

        return menu[choice]

    def _show_menu_step(self, menu: _Menu, step: Step,
                        reason: ReturnToMenu) -> Step:
        if reason.args:
            logging.warning('%s', reason)
        if step.final:
            step = menu['view']
            step.run()
        return step

    def _get_path(self, receipt_date: datetime, shop: str) -> Path:
        data_path = Path(self.settings.get('data', 'path'))
        data_format = self.settings.get('data', 'format')
        filename = data_format.format(date=receipt_date, shop=shop)
        return Path(data_path) / filename

    def _load_suggestions(self, session: Session,
                          input_source: InputSource) -> None:
        min_date = session.scalar(select(min_(Receipt.date)))
        if min_date is None:
            min_date = date.today()
        years = range(min_date.year, date.today().year + 1)
        input_source.update_suggestions({
            'shops': list(session.scalars(select(Shop.key)
                                          .order_by(Shop.key))),
            'products': list(session.scalars(select(ProductItem.label)
                                             .distinct()
                                             .order_by(ProductItem.label))),
            'discounts': list(session.scalars(select(Discount.label)
                                              .distinct()
                                              .order_by(Discount.label))),
            'meta': ['label', 'price', 'bonus'] + [
                column for column, meta in Product.__table__.c.items()
                if meta.nullable
            ],
            'indicators': [str(year) for year in years] + [
                ProductMatcher.IND_MINIMUM, ProductMatcher.IND_MAXIMUM
            ]
        })

    def run(self) -> None:
        input_source: InputSource = Prompt()
        matcher = ProductMatcher()

        with Database() as session:
            matcher.load_map(session)
            self._load_suggestions(session, input_source)

        receipt_date = input_source.get_date()
        shop = input_source.get_input('Shop', str, options='shops')
        path = self._get_path(receipt_date, shop)
        receipt = Receipt(filename=path.name, updated=datetime.now(),
                          date=receipt_date.date(), shop=shop)
        products: _ProductsMeta = set()
        write = Write(receipt, input_source, confirm=self.confirm,
                      products=products)
        write.path = path
        usage = Help(receipt, input_source)
        menu: _Menu = {
            'products': Products(receipt, input_source, matcher=matcher),
            'discounts': Discounts(receipt, input_source),
            'match': Match(receipt, input_source, matcher=matcher),
            'meta': ProductMeta(receipt, input_source, matcher=matcher),
            'view': View(receipt, input_source, products=products),
            'write': write,
            'edit': Edit(receipt, input_source,
                         editor=self.settings.get('data', 'editor')),
            'quit': Quit(receipt, input_source),
            'help': usage,
            '?': usage
        }
        usage.menu = menu
        step: Step
        for step in menu.values(): # pragma: no branch
            try:
                result = step.run()
                products.update(result.get('product_meta', {}))
                if step.final:
                    return
            except ReturnToMenu as reason:
                step = self._show_menu_step(menu, step, reason)
                break

        input_source.update_suggestions({'menu': list(menu.keys())})
        while not step.final:
            step = self._get_menu_step(menu, input_source)
            try:
                result = step.run()
                products.update(result.get('product_meta', {}))
                # Edit might change receipt metadata
                if result.get('receipt_path', False):
                    if receipt.date != receipt_date.date():
                        receipt_date = datetime.combine(receipt.date, time.min)
                    write.path = self._get_path(receipt_date, receipt.shop)
                    receipt.filename = write.path.name
            except ReturnToMenu as reason:
                step = self._show_menu_step(menu, step, reason)

"""
Subcommand to create a new receipt YAML file and import it.
"""

from datetime import datetime, time
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Optional, Sequence, TextIO, TypeVar, TYPE_CHECKING
try:
    import readline
except ImportError:
    if not TYPE_CHECKING:
        readline = None
import dateutil.parser
from sqlalchemy import select
from sqlalchemy.sql.functions import count
from .base import Base
from ..database import Database
from ..io.receipt import ReceiptReader, ReceiptWriter
from ..models.receipt import Discount, ProductItem, Receipt
from ..models.shop import Shop

Input = TypeVar('Input', str, int, float)
Menu = dict[str, 'Step']

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

        value: Optional[Input] = None
        while not isinstance(value, input_type):
            try:
                value = input_type(input(f'{name}: '))
            except ValueError as e:
                logging.warning('Invalid %s: %s', input_type.__name__, e)
        return value

    def get_date(self) -> datetime:
        date: Optional[datetime] = None
        while not isinstance(date, datetime):
            try:
                date = dateutil.parser.parse(self.get_input('Date', str))
            except ValueError as e:
                logging.warning('Invalid timestamp: %s', e)
        return date

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

    def run(self) -> bool:
        """
        Perform the step. Returns whether to update the path of the receipt
        based on receipt metadata.
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

    def run(self) -> bool:
        ok = True
        while ok:
            ok = self.add_product()

        return False

    def add_product(self) -> bool:
        """
        Request fields for a product and add it to the receipt.
        """

        quantity = self._input.get_input('Quantity (0 to end products, ? menu)',
                                         str)
        if quantity == '0':
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

    @property
    def description(self) -> str:
        return "Add products to receipt"

class Discounts(Step):
    """
    Step to add discounts.
    """

    def run(self) -> bool:
        ok = True
        self._input.update_suggestions({
            'discount_items': sorted(set(product.label
                                         for product in self._receipt.products
                                         if product.discount_indicator))
        })
        while ok:
            ok = self.add_discount()

        return False

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
                                      f'"{discount.label}", ? menu)', str,
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

class View(Step):
    """
    Step to display the receipt in its YAML representation.
    """

    def run(self) -> bool:
        writer = ReceiptWriter(Path(self._receipt.filename), (self._receipt,))
        writer.serialize(self._input.get_output())
        return False

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

    def run(self) -> bool:
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
                return update_path
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
                 path: Path, confirm: bool = False) -> None:
        super().__init__(receipt, input_source)
        self.path = path
        self._confirm = confirm

    def run(self) -> bool:
        if not self._receipt.products:
            raise ReturnToMenu('No products added to receipt')

        if self._confirm and \
            self._input.get_input('Confirm write (y)', str) != 'y':
            raise ReturnToMenu('Confirmation canceled')

        writer = ReceiptWriter(self.path, (self._receipt,))
        writer.write()
        with Database() as session:
            session.add(self._receipt)

        return False

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

    def run(self) -> bool:
        logging.info('Discarding entire receipt')
        return False

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

    def run(self) -> bool:
        output = self._input.get_output()
        choice_length = len(max(self.menu, key=len))
        for choice, step in self.menu.items():
            print(f"{choice: <{choice_length}} {step.description}", file=output)

        print("Initial characters match the first option with that prefix.",
              file=output)
        return False

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

    def _get_menu_step(self, menu: Menu, input_source: InputSource) -> Step:
        choice: Optional[str] = None
        while choice not in menu:
            choice = input_source.get_input('Menu (help or ? for usage)', str,
                                            options='menu')
            if choice not in menu:
                # Autocomplete
                choice = input_source.get_completion(choice, 0)

        return menu[choice]

    def _show_menu_step(self, menu: Menu, step: Step,
                        reason: ReturnToMenu) -> Step:
        if reason.args:
            logging.warning('%s', reason)
        if step.final:
            step = menu['view']
            step.run()
        return step

    def _get_path(self, date: datetime, shop: str) -> Path:
        data_path = Path(self.settings.get('data', 'path'))
        data_format = self.settings.get('data', 'format')
        filename = data_format.format(date=date, shop=shop)
        return Path(data_path) / filename

    def run(self) -> None:
        input_source: InputSource = Prompt()

        with Database() as session:
            input_source.update_suggestions({
                'shops': list(session.scalars(select(Shop.key)
                                              .order_by(Shop.key))),
                'products': list(session.scalars(select(ProductItem.label)
                                                 .distinct()
                                                 .order_by(ProductItem.label))),
                'discounts': list(session.scalars(select(Discount.label)
                                                  .distinct()
                                                  .order_by(Discount.label)))
            })

        date = input_source.get_date()
        shop = input_source.get_input('Shop', str, options='shops')
        path = self._get_path(date, shop)
        receipt = Receipt(filename=path.name, updated=datetime.now(),
                          date=date.date(), shop=shop)
        write = Write(receipt, input_source, path, confirm=self.confirm)
        usage = Help(receipt, input_source)
        menu: Menu = {
            'products': Products(receipt, input_source),
            'discounts': Discounts(receipt, input_source),
            'view': View(receipt, input_source),
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
                step.run()
                if step.final:
                    return
            except ReturnToMenu as reason:
                step = self._show_menu_step(menu, step, reason)
                break

        input_source.update_suggestions({'menu': list(menu.keys())})
        while not step.final:
            step = self._get_menu_step(menu, input_source)
            try:
                update_path = step.run()
                # Edit might change receipt metadata
                if update_path:
                    date = date if receipt.date == date.date() else \
                        datetime.combine(receipt.date, time.min)
                    path = self._get_path(date, receipt.shop)
                    receipt.filename = path.name
                    write.path = path
            except ReturnToMenu as reason:
                step = self._show_menu_step(menu, step, reason)

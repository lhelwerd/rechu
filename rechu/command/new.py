"""
Subcommand to create a new receipt YAML file and import it.
"""

from datetime import datetime
import logging
from pathlib import Path
import sys
from typing import Optional, Sequence, TypeVar, Union, TYPE_CHECKING
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
from ..io.receipt import ReceiptWriter
from ..models.receipt import Discount, ProductItem, Receipt
from ..models.shop import Shop

Input = TypeVar('Input', str, int, float)

@Base.register("new")
class New(Base):
    """
    Create a YAML file for a receipt and import it to the database.
    """

    def __init__(self) -> None:
        super().__init__()
        self.suggestions: dict[str, list[str]] = {}
        self.options: list[str] = []
        self.matches: list[str] = []

    def _get_input(self, name: str, input_type: type[Input],
                   options: Optional[str] = None) -> Input:
        if options is not None and options in self.suggestions:
            self.options = self.suggestions[options]
        else:
            self.options = []

        value: Optional[Input] = None
        while not isinstance(value, input_type):
            try:
                value = input_type(input(f'{name}: '))
            except ValueError as e:
                logging.warning('Invalid %s: %s', input_type.__name__, e)
        return value

    def _get_date(self) -> datetime:
        date: Optional[datetime] = None
        while not isinstance(date, datetime):
            try:
                date = dateutil.parser.parse(self._get_input('Date', str))
            except ValueError as e:
                logging.warning('Invalid timestamp: %s', e)
        return date

    def _add_products(self, receipt: Receipt) -> None:
        ok = True
        while ok:
            ok = self._add_product(receipt)

    def _add_product(self, receipt: Receipt) -> bool:
        amount = self._get_input('Quantity (0 to end product input)', str)
        if amount == '0':
            return False
        if amount.isnumeric():
            quantity: Union[str, int] = int(amount)
        else:
            quantity = amount

        label = self._get_input('Label', str, options='products')

        with Database() as session:
            self.suggestions['prices'] = [
                str(price)
                for price in session.scalars(select(ProductItem.price, count())
                                     .where(ProductItem.label == label)
                                     .group_by(ProductItem.price)
                                     .order_by(count()))
            ]
        price = self._get_input('Price', float, options='prices')

        discount = self._get_input('Discount indicator', str)
        receipt.products.append(ProductItem(quantity=quantity, label=label,
                                            price=price,
                                            discount_indicator=discount \
                                                    if discount != '' \
                                                    else None))
        return True

    def _add_discounts(self, receipt: Receipt) -> None:
        ok = True
        self.suggestions['discount_products'] = \
                sorted(set(product.label for product in receipt.products
                           if product.discount_indicator))
        while ok:
            ok = self._add_discount(receipt)

    def _add_discount(self, receipt: Receipt) -> bool:
        bonus = self._get_input('Discount label (empty to end discounts)', str,
                                options='discounts')
        if bonus == '':
            return False
        price_decrease = self._get_input('Price decrease', float)
        discount = Discount(label=bonus, price_decrease=price_decrease)
        seen = 0
        while seen < len(receipt.products):
            label = \
                self._get_input(f'Product (in order, empty to end "{bonus}")',
                                str, options='discount_products')
            if label == '':
                break
            discount_item: Optional[ProductItem] = None
            for index, product in enumerate(receipt.products[seen:]):
                if product.discount_indicator and label == product.label:
                    discount_item = product
                    discount.items.append(product)
                    seen += index + 1
                    break
            if discount_item is None:
                logging.warning('No product "%s" from #%d on receipt',
                                label, seen + 1)

        receipt.discounts.append(discount)
        return True

    def get_completion(self, text: str, state: int) -> Optional[str]:
        """
        Retrieve a completion option for the current suggestions and text state.
        """

        if state == 0:
            if text == '':
                self.matches = self.options
            else:
                self.matches = [
                    option for option in self.options if option.startswith(text)
                ]
        try:
            return self.matches[state]
        except IndexError:
            return None

    def display_matches(self, substitution: str, matches: Sequence[str],
                        longest_match_length: int) -> None:
        """
        Write a display of matches to the standard output compatible with
        readline buffers.
        """

        line_buffer = readline.get_line_buffer()
        print()

        length = int(max(map(len, matches), default=longest_match_length) * 1.2)
        template = f"{{:<{length}}}"
        buffer = ""
        for match in matches:
            display = template.format(match[len(substitution):])
            if buffer != "" and len(buffer + display) > 80:
                print(buffer)
                buffer = ""
            buffer += display

        if buffer:
            print(buffer)

        print("> ", end="")
        print(line_buffer, end="")
        sys.stdout.flush()

    def _register_readline(self) -> None:
        if readline is not None: # pragma: no cover
            readline.set_completer_delims('\t\n;')
            readline.set_completer(self.get_completion)
            readline.set_completion_display_matches_hook(self.display_matches)
            readline.parse_and_bind('tab: complete')
            readline.parse_and_bind('bind ^I rl_complete')

    def run(self) -> None:
        self._register_readline()

        with Database() as session:
            self.suggestions.update({
                'shops': list(session.scalars(select(Shop.key)
                                              .order_by(Shop.key))),
                'products': list(session.scalars(select(ProductItem.label)
                                                 .distinct()
                                                 .order_by(ProductItem.label))),
                'discounts': list(session.scalars(select(Discount.label)
                                                  .distinct()
                                                  .order_by(Discount.label)))
            })

        data_path = Path(self.settings.get('data', 'path'))
        data_format = self.settings.get('data', 'format')

        date = self._get_date()
        shop = self._get_input('Shop', str, options='shops')
        filename = data_format.format(date=date, shop=shop)
        path = Path(data_path) / filename
        receipt = Receipt(filename=path.name, updated=datetime.now(),
                          date=date.date(), shop=shop)
        self._add_products(receipt)
        if not receipt.products:
            logging.warning('No products added to receipt, discarding')
            return

        self._add_discounts(receipt)

        writer = ReceiptWriter(path, receipt)
        writer.write()
        with Database() as session:
            session.add(receipt)

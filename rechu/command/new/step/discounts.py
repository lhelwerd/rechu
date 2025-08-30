"""
Discounts step of new subcommand.
"""

import logging
import sys
from .base import ResultMeta, ReturnToMenu, Step
from ..input import InputSource
from ....matcher.product import ProductMatcher
from ....models.base import Price
from ....models.receipt import Discount, Receipt

LOGGER = logging.getLogger(__name__)

class Discounts(Step):
    """
    Step to add discounts.
    """

    def __init__(self, receipt: Receipt, input_source: InputSource,
                 matcher: ProductMatcher, more: bool = False) -> None:
        super().__init__(receipt, input_source)
        self._matcher = matcher
        self._more = more

    def run(self) -> ResultMeta:
        self._matcher.discounts = True
        self._update_suggestions()

        discount_items = sum(len(product.discount_indicators)
                             for product in self._receipt.products)
        discounted_products = sum(
            len(discount.items) for discount in self._receipt.discounts
        )
        LOGGER.info('%d/%d discounted items already matched on receipt',
                    discounted_products, discount_items)
        ok = True
        while ok and (self._more or discounted_products < discount_items):
            ok = self.add_discount()
            discounted_products = sum(
                len(discount.items) for discount in self._receipt.discounts
            )

        return {}

    def _update_suggestions(self) -> None:
        discount_items = {
            product.label for product in self._receipt.products
            if self._more or
            len(product.discount_indicators) > len(product.discounts)
        }
        self._input.update_suggestions({
            'discount_items': sorted(discount_items)
        })

    def add_discount(self) -> bool:
        """
        Request fields and items for a discount and add it to the receipt.
        """

        prompt = 'Discount label (empty to end discounts, ? to menu, ! cancels)'
        bonus = self._input.get_input(prompt, str, options='discounts')

        if bonus == '':
            return False
        if bonus == '?':
            raise ReturnToMenu
        if bonus == '!':
            if self._receipt.discounts:
                LOGGER.info('Removing previous discount: %r',
                            self._receipt.discounts[-1])
                self._receipt.discounts[-1].items = []
                self._receipt.discounts.pop()
            return True

        price = self._input.get_input('Price decrease (positive cancels)',
                                      Price)
        if price > 0:
            return True

        discount = Discount(label=bonus, price_decrease=price,
                            position=len(self._receipt.discounts))

        seen = 0
        last_discounted = len(self._receipt.products) if self._more else \
            max(index + 1 for index, item in enumerate(self._receipt.products)
                if len(item.discount_indicators) > len(item.discounts))

        try:
            while 0 <= seen < last_discounted:
                seen = self.add_discount_item(discount, seen)
        finally:
            if seen >= 0:
                self._receipt.discounts.append(discount)
            else:
                discount.items = []

        return True

    def add_discount_item(self, discount: Discount, seen: int) -> int:
        """
        Request fields for a discount item.
        """

        self._update_suggestions()
        label = self._input.get_input('Product (in order on receipt, empty to '
                                      f'end "{discount.label}", ? to menu, ! '
                                      'cancels)', str, options='discount_items')
        if label == '':
            return sys.maxsize
        if label == '?':
            raise ReturnToMenu
        if label == '!':
            return -1

        for index, product in enumerate(self._receipt.products[seen:]):
            if product.discount_indicator and label == product.label:
                discount.items.append(product)
                seen += index + 1
                break
        else:
            LOGGER.warning('No discounted product "%s" from #%d (%r)',
                           label, seen + 1, self._receipt.products[seen:])

        return seen

    @property
    def description(self) -> str:
        return "Add discounts to receipt"

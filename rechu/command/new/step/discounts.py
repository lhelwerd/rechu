"""
Discounts step of new subcommand.
"""

from dataclasses import dataclass
import logging
import sys
from typing_extensions import override
from .base import ResultMeta, ReturnToMenu, Step
from ....matcher.product import ProductMatcher
from ....models.base import Price
from ....models.receipt import Discount

LOGGER = logging.getLogger(__name__)


@dataclass
class Discounts(Step):
    """
    Step to add discounts.
    """

    matcher: ProductMatcher
    more: bool = False

    @override
    def run(self) -> ResultMeta:
        self.matcher.discounts = True
        self._update_suggestions()

        discount_items = sum(
            len(product.discount_indicators)
            for product in self.receipt.products
        )
        discounted_products = sum(
            len(discount.items) for discount in self.receipt.discounts
        )
        LOGGER.info(
            "%d/%d discounted items already matched on receipt",
            discounted_products,
            discount_items,
        )
        ok = True
        while ok and (self.more or discounted_products < discount_items):
            ok = self.add_discount()
            discounted_products = sum(
                len(discount.items) for discount in self.receipt.discounts
            )

        return {}

    def _update_suggestions(self) -> None:
        discount_items = {
            product.label
            for product in self.receipt.products
            if self.more
            or len(product.discount_indicators) > len(product.discounts)
        }
        self.input.update_suggestions(
            {"discount_items": sorted(discount_items)}
        )

    def add_discount(self) -> bool:
        """
        Request fields and items for a discount and add it to the receipt.
        """

        prompt = "Discount label (empty to end discounts, ? to menu, ! cancels)"
        bonus = self.input.get_input(prompt, str, options="discounts")

        if bonus == "":
            return False
        if bonus == "?":
            raise ReturnToMenu
        if bonus == "!":
            if self.receipt.discounts:
                LOGGER.info(
                    "Removing previous discount: %r", self.receipt.discounts[-1]
                )
                self.receipt.discounts[-1].items = []
                _ = self.receipt.discounts.pop()
            return True

        price = self.input.get_input("Price decrease (positive cancels)", Price)
        if price > 0:
            return True

        discount = Discount(
            label=bonus,
            price_decrease=price,
            position=len(self.receipt.discounts),
        )

        seen = 0
        last_discounted = (
            len(self.receipt.products)
            if self.more
            else max(
                index + 1
                for index, item in enumerate(self.receipt.products)
                if len(item.discount_indicators) > len(item.discounts)
            )
        )

        try:
            while 0 <= seen < last_discounted:
                seen = self.add_discount_item(discount, seen)
        finally:
            if seen >= 0:
                self.receipt.discounts.append(discount)
            else:
                discount.items = []

        return True

    def add_discount_item(self, discount: Discount, seen: int) -> int:
        """
        Request fields for a discount item.
        """

        self._update_suggestions()
        label = self.input.get_input(
            (
                "Product (in order on receipt, empty to "
                f'end "{discount.label}", ? to menu, ! '
                "cancels)"
            ),
            str,
            options="discount_items",
        )
        if label == "":
            return sys.maxsize
        if label == "?":
            raise ReturnToMenu
        if label == "!":
            return -1

        for index, product in enumerate(self.receipt.products[seen:]):
            if product.discount_indicator and label == product.label:
                discount.items.append(product)
                seen += index + 1
                break
        else:
            LOGGER.warning(
                'No discounted product "%s" from #%d (%r)',
                label,
                seen + 1,
                self.receipt.products[seen:],
            )

        return seen

    @property
    @override
    def description(self) -> str:
        return "Add discounts to receipt"

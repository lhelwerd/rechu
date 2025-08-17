"""
Products step of new subcommand.
"""

import logging
from typing import Optional, Union
from sqlalchemy import select
from sqlalchemy.sql.functions import count
from .base import Pairs, ResultMeta, ReturnToMenu, Step
from .meta import ProductMeta
from ..input import InputSource
from ....database import Database
from ....matcher.product import ProductMatcher
from ....models.base import Price, Quantity
from ....models.receipt import ProductItem, Receipt
from ....models.product import Product

LOGGER = logging.getLogger(__name__)

class Products(Step):
    """
    Step to add products.
    """

    def __init__(self, receipt: Receipt, input_source: InputSource,
                 matcher: ProductMatcher) -> None:
        super().__init__(receipt, input_source)
        self._matcher = matcher

    def run(self) -> ResultMeta:
        self._matcher.discounts = bool(self._receipt.discounts)
        ok = True
        first = True
        while ok:
            ok = self.add_product(first)
            first = False

        return {}

    def add_product(self, first: bool = False) -> bool:
        """
        Request fields for a product and add it to the receipt.
        """

        prompt = 'Quantity (empty or 0 to end products, ? to menu, ! cancels)'
        if self._receipt.products and not first:
            previous = self._receipt.products[-1]
            # Check if the previous product item has a product metadata match
            # If not, we might want to create one right now
            with Database() as session:
                pairs = tuple(self._matcher.find_candidates(
                    session, (previous,), self._get_products_meta(session)
                ))
                dedupe = tuple(self._matcher.filter_duplicate_candidates(pairs))
                amount = self._make_meta(previous, prompt, pairs, dedupe)
        else:
            amount = self._input.get_input(prompt, str)

        if amount in {'', '0'}:
            return False
        if amount == '?':
            raise ReturnToMenu
        if amount == '!':
            LOGGER.info('Removing previous product: %r',
                        self._receipt.products[-1:])
            self._receipt.products[-1:] = []
            return True

        try:
            quantity = Quantity(amount)
        except ValueError as error:
            LOGGER.error("Could not validate quantity: %s", error)
            return True

        label = self._input.get_input('Label (empty or ! cancels)', str,
                                      options='products')
        if label in {'', '!'}:
            return True

        with Database() as session:
            self._input.update_suggestions({'prices': [
                str(price)
                for price in session.scalars(select(ProductItem.price, count())
                                     .where(ProductItem.label == label)
                                     .group_by(ProductItem.price)
                                     .order_by(count()))
            ]})
        price = self._input.get_input('Price (negative cancels)', Price,
                                      options='prices')
        if price < 0:
            return True

        discount = self._input.get_input('Discount indicator (! cancels)', str)
        if discount != '!':
            position = len(self._receipt.products)
            item = ProductItem(quantity=quantity,
                               label=label,
                               price=price,
                               discount_indicator=(
                                   discount if discount != '' else None
                               ),
                               position=position,
                               amount=quantity.amount,
                               unit=quantity.unit)
            self._receipt.products.append(item)
        return True

    def _make_meta(self, item: ProductItem, prompt: str,
                   pairs: Pairs, dedupe: Pairs) -> Union[str, Quantity]:
        match_prompt = 'No metadata yet'
        product: Optional[Product] = None
        if dedupe:
            if dedupe[0][0].discounts:
                LOGGER.info('Matched with %r excluding discounts', dedupe[0][0])
            else:
                LOGGER.info('Matched with %r', dedupe[0][0])

            if dedupe[0][0].generic is None:
                product = self._matcher.check_map(dedupe[0][0])
                match_prompt = 'Matched metadata can be augmented'
            else:
                match_prompt = 'More metadata accepted'
        elif len(pairs) > 1:
            LOGGER.warning('Multiple metadata matches: %r', pairs)
            match_prompt = 'More metadata accepted, may merge to deduplicate'

        add_product = True
        while add_product:
            meta_prompt = f'{match_prompt}. Next {prompt.lower()} or key'
            key = self._input.get_input(meta_prompt, str, options='meta')
            if key in {'', '?', '!'} or key[0].isnumeric():
                # Quantity or other product item command
                return key

            meta = ProductMeta(self._receipt, self._input,
                               matcher=self._matcher)
            add_product = meta.add_product(item=item, initial_key=key,
                                           product=product)[0]

        return self._input.get_input(prompt, str)

    @property
    def description(self) -> str:
        return "Add products to receipt"

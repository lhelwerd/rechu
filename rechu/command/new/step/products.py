"""
Products step of new subcommand.
"""

from dataclasses import dataclass
import logging
import re
from typing import Optional, Union
from typing_extensions import override
from sqlalchemy import select
from sqlalchemy.sql.functions import count
from .base import Pairs, ResultMeta, ReturnToMenu, Step
from .meta import ProductMeta
from ....database import Database
from ....matcher.product import ProductMatcher
from ....models.base import Price, Quantity
from ....models.receipt import ProductItem
from ....models.product import Product

LOGGER = logging.getLogger(__name__)


@dataclass
class Products(Step):
    """
    Step to add products.
    """

    matcher: ProductMatcher

    @override
    def run(self) -> ResultMeta:
        self.matcher.discounts = bool(self.receipt.discounts)
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

        prompt = "Quantity (empty or 0 to end products, ? to menu, ! cancels)"
        if self.receipt.products and not first:
            previous = self.receipt.products[-1]
            # Check if the previous product item has a product metadata match
            # If not, we might want to create one right now
            with Database() as session:
                pairs = tuple(
                    self.matcher.find_candidates(
                        session, (previous,), self._get_products_meta(session)
                    )
                )
                dedupe = tuple(self.matcher.filter_duplicate_candidates(pairs))
                amount = self._make_meta(previous, prompt, pairs, dedupe)
        else:
            amount = self.input.get_input(prompt, str)

        if amount in {"", "0"}:
            return False
        if amount == "?":
            raise ReturnToMenu
        if amount == "!":
            LOGGER.info(
                "Removing previous product: %r", self.receipt.products[-1:]
            )
            self.receipt.products[-1:] = []
            return True

        try:
            quantity = Quantity(amount)
        except (ValueError, AssertionError):
            LOGGER.exception("Could not validate quantity: %s", amount)
            return True

        label = self.input.get_input(
            "Label (empty or ! cancels)", str, options="products"
        )
        if label in {"", "!"}:
            return True

        self._update_suggestions(label)
        price = self.input.get_input(
            "Price (negative cancels)", Price, options="prices"
        )
        if price < 0:
            return True

        discount = self.input.get_input(
            "Discount indicator (! cancels)", str, options="discount_indicators"
        )
        if discount != "!":
            position = len(self.receipt.products)
            item = ProductItem(
                quantity=quantity,
                label=label,
                price=price,
                discount_indicator=(discount if discount != "" else None),
                position=position,
                amount=quantity.amount,
                unit=quantity.unit,
            )
            self.receipt.products.append(item)
        return True

    def _update_suggestions(self, label: str) -> None:
        with Database() as session:
            prices = session.scalars(
                select(ProductItem.price)
                .where(ProductItem.label == label)
                .group_by(ProductItem.price)
                .order_by(count())
            )
            discount_indicators: list[str] = [
                str(indicator)
                for indicator in session.scalars(
                    select(ProductItem.discount_indicator)
                    .where(ProductItem.label == label)
                    .where(ProductItem.discount_indicator.is_not(None))
                    .order_by(ProductItem.discount_indicator)
                    .distinct()
                )
            ]
            if not discount_indicators:
                discount_indicators = [
                    indicator.pattern
                    for indicator in self.receipt.shop_meta.discount_indicators
                    if re.escape(indicator.pattern) == indicator.pattern
                ]
            self.input.update_suggestions(
                {
                    "prices": [str(price) for price in prices],
                    "discount_indicators": discount_indicators,
                }
            )

    @staticmethod
    def _overlap_discounts(pairs: Pairs) -> bool:
        discounts: set[str] = set()
        seen: set[Product] = set()
        for pair in pairs:
            labels = {discount.label for discount in pair[0].discounts}
            if not discounts.isdisjoint(labels) and (
                (generic := pair[0].generic) is None
                or labels != {discount.label for discount in generic.discounts}
            ):
                return True
            discounts.update(labels)
            seen.add(pair[0])

        return False

    def _make_meta(
        self, item: ProductItem, prompt: str, pairs: Pairs, dedupe: Pairs
    ) -> Union[str, Quantity]:
        match_prompt = "No metadata yet"
        product: Optional[Product] = None
        if dedupe:
            if not self.matcher.discounts and dedupe[0][0].discounts:
                LOGGER.info(
                    "Matched with %r assuming later discounts", dedupe[0][0]
                )
            else:
                LOGGER.info("Matched with %r", dedupe[0][0])

            if dedupe[0][0].generic is None:
                product = self.matcher.check_map(dedupe[0][0])
                match_prompt = "Matched metadata can be augmented"
            else:
                match_prompt = "More metadata accepted"
        elif len(pairs) > 1:
            if self.matcher.discounts or self._overlap_discounts(pairs):
                LOGGER.warning("Multiple metadata matches: %r", pairs)
            else:
                LOGGER.info(
                    "Matched with one of %r assuming later discounts", pairs
                )
            match_prompt = "More metadata accepted, may merge to deduplicate"

        add_product = True
        while add_product:
            meta_prompt = f"{match_prompt}. Next {prompt.lower()} or key"
            key = self.input.get_input(meta_prompt, str, options="meta")
            if key in {"", "?", "!"} or key[0].isnumeric():
                # Quantity or other product item command
                return key

            meta = ProductMeta(self.receipt, self.input, matcher=self.matcher)
            add_product = meta.add_product(
                item=item, initial_key=key, product=product
            )[0]

        return self.input.get_input(prompt, str)

    @property
    @override
    def description(self) -> str:
        return "Add products to receipt"

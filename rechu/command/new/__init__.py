"""
Subcommand to create a new receipt YAML file and import it.
"""

from datetime import datetime, date, time, timedelta
from pathlib import Path
from typing import ClassVar, Optional, cast, final
from typing_extensions import override
from sqlalchemy import Row, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.functions import min as min_, max as max_
from .input import InputSource, Prompt
from .step import (
    Menu,
    ReturnToMenu,
    Step,
    Read,
    Products,
    Discounts,
    ProductMeta,
    View,
    Write,
    Edit,
    Quit,
    Help,
)
from ..base import Base, SubparserArguments, SubparserKeywords
from ...database import Database
from ...io.products import OPTIONAL_FIELDS
from ...matcher.product import Indicator, ProductMatcher
from ...models.receipt import Discount, ProductItem, Receipt
from ...models.shop import Shop


class _DateRow(Row[tuple[date, date]]):
    """
    Result row of query of date ranges of receipts.
    """

    min: Optional[date]
    max: date


@final
@Base.register("new")
class New(Base):
    """
    Create a YAML file for a receipt and import it to the database.
    """

    subparser_keywords: ClassVar[SubparserKeywords] = {
        "help": "Create receipt file and import",
        "description": (
            "Interactively fill in a YAML file for a receipt and "
            "import it to the database."
        ),
    }
    subparser_arguments: ClassVar[SubparserArguments] = [
        (
            ("-c", "--confirm"),
            {
                "action": "store_true",
                "default": False,
                "help": "Confirm before updating database files or exiting",
            },
        ),
        (
            ("-m", "--more"),
            {
                "action": "store_true",
                "default": False,
                "help": "Allow more discounts and metadata than product items",
            },
        ),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.confirm: bool = False
        self.more: bool = False

    def _get_menu_step(self, menu: Menu, input_source: InputSource) -> Step:
        choice: Optional[str] = None
        while choice not in menu:
            choice = input_source.get_input(
                "Menu (help or ? for usage)", str, options="menu"
            )
            if choice != "" and choice not in menu:
                # Autocomplete
                choice = input_source.get_completion(choice, 0)

        return menu[choice]

    def _show_menu_step(
        self, menu: Menu, step: Step, reason: ReturnToMenu
    ) -> Step:
        if reason.msg:
            self.logger.warning("%s", reason.msg)
        if step.final:
            step = menu["view"]
            _ = step.run()
        return step

    def _confirm_final(self, step: Step, input_source: InputSource) -> None:
        if self.confirm and step.final:
            prompt = f"Confirm that you want to {step.description.lower()} (y)"
            if input_source.get_input(prompt, str) != "y":
                raise ReturnToMenu("Confirmation canceled")

    def _get_path(self, receipt_date: datetime, shop: str) -> Path:
        data_path = Path(self.settings.get("data", "path"))
        data_format = self.settings.get("data", "format")
        filename = data_format.format(date=receipt_date, shop=shop)
        return Path(data_path) / filename

    def _load_date_suggestions(
        self, session: Session, input_source: InputSource
    ) -> None:
        indicators = [str(Indicator.MINIMUM), str(Indicator.MAXIMUM)]
        dates = cast(
            Optional[_DateRow],
            session.execute(
                select(
                    min_(Receipt.date).label("min"),
                    max_(Receipt.date).label("max"),
                )
            ).first(),
        )
        if dates is None or dates.min is None:
            input_source.update_suggestions({"indicators": indicators})
            return

        today = date.today()
        years = range(dates.min.year, today.year + 1)
        input_source.update_suggestions(
            {
                "days": [
                    str(dates.max + timedelta(days=day))
                    for day in range(max(0, (today - dates.max).days) + 1)
                ],
                "indicators": [str(year) for year in years] + indicators,
            }
        )

    def _load_suggestions(
        self, session: Session, input_source: InputSource
    ) -> None:
        self._load_date_suggestions(session, input_source)
        input_source.update_suggestions(
            {
                "shops": list(
                    session.scalars(select(Shop.key).order_by(Shop.key))
                ),
                "meta": [
                    "label",
                    "price",
                    "discount",
                    *OPTIONAL_FIELDS,
                    "range",
                    "view",
                ],
            }
        )

    def _load_shop_suggestions(
        self, session: Session, input_source: InputSource, shop: str
    ) -> None:
        input_source.update_suggestions(
            {
                "products": list(
                    session.scalars(
                        select(ProductItem.label)
                        .distinct()
                        .join(Receipt)
                        .filter(Receipt.shop == shop)
                        .order_by(ProductItem.label)
                    )
                ),
                "discounts": list(
                    session.scalars(
                        select(Discount.label)
                        .distinct()
                        .join(Receipt)
                        .filter(Receipt.shop == shop)
                        .order_by(Discount.label)
                    )
                ),
            }
        )

    @override
    def run(self) -> None:
        input_source: InputSource = Prompt()
        matcher = ProductMatcher()
        matcher.discounts = False

        with Database() as session:
            self._load_suggestions(session, input_source)

            receipt_date = input_source.get_date(
                datetime.combine(date.today(), time.min)
            )
            shop = input_source.get_input("Shop", str, options="shops")

            self._load_shop_suggestions(session, input_source, shop)

        path = self._get_path(receipt_date, shop)
        receipt = Receipt(
            filename=path.name,
            updated=datetime.now(),
            date=receipt_date.date(),
            shop=shop,
        )
        write = Write(receipt, input_source, matcher=matcher)
        write.path = path
        usage = Help(receipt, input_source)
        menu: Menu = {
            "read": Read(receipt, input_source, matcher=matcher),
            "products": Products(receipt, input_source, matcher=matcher),
            "discounts": Discounts(
                receipt, input_source, matcher=matcher, more=self.more
            ),
            "meta": ProductMeta(
                receipt, input_source, matcher=matcher, more=self.more
            ),
            "view": View(receipt, input_source),
            "write": write,
            "edit": Edit(
                receipt,
                input_source,
                matcher=matcher,
                editor=self.settings.get("data", "editor"),
            ),
            "quit": Quit(receipt, input_source),
            "help": usage,
            "?": usage,
        }
        usage.menu = menu
        step = self._run_sequential(menu, input_source)
        if step.final:
            return

        # Sequential run did not lead to a final step, so ask for menu choice
        input_source.update_suggestions({"menu": list(menu.keys())})
        while not step.final:
            step = self._get_menu_step(menu, input_source)
            try:
                self._confirm_final(step, input_source)
                result = step.run()
                # Edit might change receipt metadata
                if result.get("receipt_path", False):
                    if receipt.date != receipt_date.date():
                        receipt_date = datetime.combine(receipt.date, time.min)
                    write.path = self._get_path(receipt_date, receipt.shop)
                    receipt.filename = write.path.name
            except ReturnToMenu as reason:
                step = self._show_menu_step(menu, step, reason)

    def _run_sequential(self, menu: Menu, input_source: InputSource) -> Step:
        if not menu:  # pragma: no cover
            raise ValueError("Menu must have defined steps")
        steps = list(menu.values())
        step = steps[0]
        for step in steps:  # pragma: no branch
            try:
                self._confirm_final(step, input_source)
                _ = step.run()
                if step.final:
                    return step
            except ReturnToMenu as reason:
                step = self._show_menu_step(menu, step, reason)
                break

        return step

"""
Edit step of new subcommand.
"""

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from typing_extensions import override

from ....database import Database
from ....io.receipt import ReceiptReader, ReceiptWriter
from ....matcher.product import ProductMatcher
from ....models.receipt import Receipt
from .base import ResultMeta, ReturnToMenu, Step


@dataclass
class Edit(Step):
    """
    Step to edit the receipt in its YAML representation via a temporary file.
    """

    matcher: ProductMatcher
    editor: str | None = None

    @override
    def run(self) -> ResultMeta:
        with tempfile.NamedTemporaryFile("w", suffix=".yml") as tmp_file:
            tmp_path = Path(tmp_file.name)
            writer = ReceiptWriter(tmp_path, (self.receipt,))
            writer.write()

            self.execute_editor(tmp_file.name)

            reader = ReceiptReader(tmp_path, updated=self.receipt.updated)
            try:
                receipt = next(reader.read())

                # Bring over any product metadata that still matches items
                self._update_matches(receipt)

                # Replace receipt
                update_path = (
                    self.receipt.date != receipt.date
                    or self.receipt.shop != receipt.shop
                )
                self.receipt.date = receipt.date
                self.receipt.shop = receipt.shop
                self.receipt.products = receipt.products
                self.receipt.discounts = receipt.discounts
            except (StopIteration, TypeError, ValueError) as error:
                raise ReturnToMenu(
                    "Invalid or missing edited receipt YAML"
                ) from error

            return {"receipt_path": update_path}

    def _update_matches(self, receipt: Receipt) -> None:
        with Database() as session:
            products = self._get_products_meta(session)
            pairs = self.matcher.find_candidates(
                session, receipt.products, products
            )
            for meta, match in self.matcher.filter_duplicate_candidates(pairs):
                if meta in products:
                    match.product = meta

    def execute_editor(self, filename: str) -> None:
        """
        Open an editor to edit the provided filename.
        """

        # Find editor which can be found in the PATH
        editors = [
            self.editor,
            os.getenv("VISUAL"),
            os.getenv("EDITOR"),
            "editor",
            "vim",
        ]
        for editor in editors:
            if (
                editor is not None
                and shutil.which(editor.split(" ", 1)[0]) is not None
            ):
                break
        else:
            raise ReturnToMenu("No editor executable found")

        # Spawn selected editor
        try:
            _ = subprocess.run([*editor.split(" "), filename], check=True)
        except subprocess.CalledProcessError as exit_status:
            raise ReturnToMenu(
                "Editor returned non-zero exit status"
            ) from exit_status

    @property
    @override
    def description(self) -> str:
        return "Edit the current receipt via its YAML format"

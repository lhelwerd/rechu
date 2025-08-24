"""
Edit step of new subcommand.
"""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Optional
from .base import ResultMeta, ReturnToMenu, Step
from ..input import InputSource
from ....database import Database
from ....io.receipt import ReceiptReader, ReceiptWriter
from ....matcher.product import ProductMatcher
from ....models.receipt import Receipt

class Edit(Step):
    """
    Step to edit the receipt in its YAML representation via a temporary file.
    """

    def __init__(self, receipt: Receipt, input_source: InputSource,
                 matcher: ProductMatcher,
                 editor: Optional[str] = None) -> None:
        super().__init__(receipt, input_source)
        self._matcher = matcher
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

                # Bring over any product metadata that still matches items
                self._update_matches(receipt)

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

    def _update_matches(self, receipt: Receipt) -> None:
        with Database() as session:
            products = self._get_products_meta(session)
            pairs = self._matcher.find_candidates(session,
                                                  receipt.products,
                                                  products)
            for meta, match in self._matcher.filter_duplicate_candidates(pairs):
                if meta in products:
                    match.product = meta

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

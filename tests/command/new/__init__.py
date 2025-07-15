"""
Tests of subcommand to create a new receipt YAML file and import it.
"""

from collections.abc import Generator, Iterable
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, date
import os
from pathlib import Path
from subprocess import CalledProcessError
from typing import Optional
from unittest.mock import MagicMock, call, patch
from sqlalchemy import select
from sqlalchemy.orm import Session
import yaml
from rechu.command.new import New, InputSource, Prompt, Step
from rechu.inventory.products import Products
from rechu.io.products import ProductsReader
from rechu.io.receipt import ReceiptReader
from rechu.models.base import Price, Quantity
from rechu.models.product import Product, LabelMatch, PriceMatch, DiscountMatch
from rechu.models.receipt import Receipt, ProductItem
from ...database import DatabaseTestCase

_ExpectedProducts = tuple[Optional[Product], ...]

INPUT_MODULE = "rechu.command.new.input"

class NewTest(DatabaseTestCase):
    """
    Test creating a YAML file and importing it to the database.
    """

    inventory = Path("samples/products-id.yml")
    edit = Path("samples/new/receipt_edit_input")
    expected = Path("samples/receipt.yml")
    create_invalid = Path("samples/2024-11-01-12-34-inv.yml")
    expected_invalid = Path("samples/expected-invalid-receipt.yml")
    expected_inventory = Path("samples/products-inv.yml")
    create = Path("samples/2024-11-01-12-34-id.yml")
    copy = Path("samples/2024-11-01-00-00-id.yml")

    def _delete_files(self) -> None:
        # Remove temporary input and output receipts and extra inventories.
        self.create.unlink(missing_ok=True)
        self.copy.unlink(missing_ok=True)
        self.create_invalid.unlink(missing_ok=True)
        self.expected_invalid.unlink(missing_ok=True)
        self.expected_inventory.unlink(missing_ok=True)

    def setUp(self) -> None:
        super().setUp()

        self.products = tuple(ProductsReader(self.inventory).read())
        self.expected_products: _ExpectedProducts = (
            None, self.products[2].range[1], None, self.products[2],
            self.products[0], self.products[1]
        )
        self.replaces: list[tuple[str, str]] = []
        self._replace = iter(self.replaces)
        self._delete_files()

    def tearDown(self) -> None:
        super().tearDown()
        self._delete_files()

    @contextmanager
    def _setup_input(self, input_path: Path,
                     start_inputs: Iterable[str] = ("y",),
                     end_inputs: Iterable[str] = ()) -> Generator[MagicMock]:
        with input_path.open("r", encoding="utf-8") as input_file:
            inputs = [line.rstrip() for line in input_file]
            inputs[2:2] = start_inputs
            inputs.extend(end_inputs)
            with patch(f"{INPUT_MODULE}.input", side_effect=inputs) as mock:
                yield mock

    def test_run(self) -> None:
        """
        Test executing the command.
        """

        # The same receipt in the database with different filename is ignored.
        with self.database as session:
            receipt = next(ReceiptReader(self.expected).read())
            session.add(receipt)

        with self._setup_input(Path("samples/new/receipt_input")):
            command = New()
            command.run()
            self._compare_expected_receipt(self.create, self.expected,
                                           self.expected_products)

    def _compare_expected_receipt(self, path: Path, expected: Path,
                                  products_match: _ExpectedProducts,
                                  check_product_inventory: bool = True) -> None:
        with expected.open("r", encoding="utf-8") as receipt_file:
            expected_receipt = yaml.safe_load(receipt_file)
            # Drop missing discount product label
            if expected_receipt['bonus'][-1][0] == 'missing':
                expected_receipt['bonus'][-1].pop()

        with self.database as session:
            query = select(Receipt).filter(Receipt.filename == path.name)
            receipt = session.scalars(query).first()
            if receipt is None:
                self.fail("Expected receipt to be stored")
            self.assertEqual(receipt.filename, path.name)
            self.assertGreaterEqual(len(receipt.products), len(products_match))
            for index, (match, item) in enumerate(zip(products_match,
                                                      receipt.products)):
                with self.subTest(index=index):
                    self._check_match(match, item)

            self.assertTrue(path.exists())
            self.assertEqual(datetime.fromtimestamp(path.stat().st_mtime),
                             receipt.updated)
            with path.open("r", encoding="utf-8") as new_file:
                self.assertEqual(expected_receipt, yaml.safe_load(new_file))

            if check_product_inventory:
                self._check_product_inventory(session, products_match)

    def _check_match(self, match: Optional[Product], item: ProductItem) -> None:
        if match is None:
            self.assertIsNone(item.product)
        elif item.product is None:
            self.fail(f"Expected {item!r} to match {match!r}")
        else:
            product_copy = match.copy()
            product_copy.id = item.product.id
            product_copy.generic_id = item.product.generic_id
            for range_copy, range_item in zip(product_copy.range,
                                              item.product.range):
                range_copy.id = range_item.id
                range_copy.generic_id = range_item.generic_id
                self.assertEqual(range_item.generic_id, item.product.id)
            self.assertFalse(product_copy.merge(item.product),
                             f"{item!r} should be matched to {match!r}, "
                             f"instead the match is {item.product!r}")

    def _match_product(self, match: Product, product: Product) -> bool:
        if match.labels and product.labels:
            return match.labels[0].name == product.labels[0].name
        if match.sku and product.sku:
            return match.sku == product.sku
        if match.gtin and product.gtin:
            return match.gtin == product.gtin
        return False

    def _check_product_inventory(self, session: Session,
                                 products_match: _ExpectedProducts) -> None:
        actual_products = \
            list(session.scalars(select(Product)
                                 .filter(Product.generic_id.is_(None))).all())
        expected_products: set[Product] = {
            product for product in set(self.products) | set(products_match)
            if product is not None and product.generic is None
        }
        self.assertEqual(len(actual_products),
                         len(expected_products),
                         f"{actual_products!r} is not {expected_products!r}")

        # Test if the product metadata is written to the correct inventory.
        for path, products in Products.spread(expected_products).items():
            if not any(product in products for product in products_match):
                # Inventory was not created/updated as part of this test
                continue

            self.assertTrue(path.exists(), f"Inventory {path} is created")
            actual = tuple(ProductsReader(path).read())
            self.assertEqual(len(products), len(actual))
            for index, product in enumerate(actual):
                with self.subTest(index=index):
                    # The inventory does not have an order so find by label,
                    # sku or gtin.
                    product_matches = [
                        match for match in products
                        if self._match_product(match, product)
                    ]
                    self.assertEqual(len(product_matches), 1)
                    match = product_matches[0]
                    self.assertFalse(match.copy().merge(product),
                                     f"{product!r} is not same as {match!r}")

    def _check_no_receipt(self, path: Path) -> None:
        with self.database as session:
            query = select(Receipt).filter(Receipt.filename == path.name)
            receipt = session.scalars(query).first()
            self.assertIsNone(receipt)
            self._check_product_inventory(session, tuple())

        self.assertFalse(path.exists())

    def _get_replace(self) -> tuple[str, str]:
        try:
            return next(self._replace)
        except StopIteration:
            return ('', '')

    def _edit_file(self, args: list[str], check: bool = False) -> None:
        # pylint: disable=unused-argument
        with Path(args[-1]).open('r+', encoding='utf-8') as tmp_file:
            replace = self._get_replace()
            lines = [line.replace(*replace) for line in tmp_file]
            tmp_file.seek(0)
            for line in lines:
                tmp_file.write(line)
            tmp_file.truncate()

    def _copy_file(self, args: list[str], check: bool = False) -> None:
        # pylint: disable=unused-argument
        with self.expected.open('r', encoding='utf-8') as input_file:
            with Path(args[-1]).open('w', encoding='utf-8') as tmp_file:
                tmp_file.write(input_file.read().replace(*self._get_replace()))

    @staticmethod
    def _clear_file(args: list[str], check: bool = False) -> None:
        # pylint: disable=unused-argument
        with Path(args[-1]).open('w', encoding='utf-8') as tmp_file:
            tmp_file.write('')

    def test_run_duplicate_product_meta(self) -> None:
        """
        Test executing the command with duplicate product metadata models
        stored in the database, causing none of the receipt products to match.
        """

        # Preload the products twice
        with self.database as session:
            session.add_all(deepcopy(self.products))
            session.add_all(deepcopy(self.products))

        with self._setup_input(Path("samples/new/receipt_input")):
            command = New()
            command.run()
            unmatched_products = (None,) * len(self.expected_products)
            self._compare_expected_receipt(self.create, self.expected,
                                           unmatched_products,
                                           check_product_inventory=False)

    def test_run_stale_product_meta(self) -> None:
        """
        Test executing the command with additional product metadata models
        stored in the database, which are deleted once they are found to not
        be in the file-based inventory.
        """

        # Preload the products and add another model
        with self.database as session:
            session.add_all(deepcopy(self.products))
            session.add(Product(shop='id',
                                labels=[LabelMatch(name='unmatched')],
                                prices=[PriceMatch(value=Price('9.87'))],
                                sku='zz123',
                                gtin=5555555555555))

        with self._setup_input(Path("samples/new/receipt_input")):
            command = New()
            command.run()
            self._compare_expected_receipt(self.create, self.expected,
                                           self.expected_products)

    def test_run_edit_clear(self) -> None:
        """
        Test executing the command with an edit in between that clears the file.
        """

        with self._setup_input(self.edit, end_inputs=["quit"]):
            with patch("subprocess.run", side_effect=self._clear_file) as clear:
                command = New()
                command.run()
                clear.assert_called_once()
                self._check_no_receipt(self.copy)

    def test_run_edit_no_editor(self) -> None:
        """
        Test executing the command with an edit in between but with no editor
        in the PATH.
        """

        with self._setup_input(self.edit, end_inputs=["quit"]):
            with patch("subprocess.run",
                       side_effect=self._copy_file) as copy_cmd:
                environment = {
                    'RECHU_DATA_EDITOR': '/usr/bin/unittest edit -c 1',
                    'EDITOR': 'nano'
                }
                with patch.dict("os.environ", environment):
                    os.environ.pop('VISUAL', None)
                    with patch("shutil.which", return_value=None) as which:
                        command = New()
                        command.run()
                        copy_cmd.assert_not_called()
                        self.assertEqual(which.call_args_list, [
                            call("/usr/bin/unittest"), call("nano"),
                            call("editor"), call("vim")
                        ])
                        self._check_no_receipt(self.copy)

    def test_run_edit_error(self) -> None:
        """
        Test executing the command with an edit in between where the editor
        executable has a non-zero exit status.
        """

        with patch.dict('os.environ', {'RECHU_DATA_EDITOR': '/bin/ut ed -c 1'}):
            with self._setup_input(self.edit, end_inputs=["quit"]):
                error = CalledProcessError(1, '/bin/ut')
                with patch("subprocess.run", side_effect=error) as run:
                    with patch("shutil.which", return_value='/bin/ut'):
                        command = New()
                        command.run()
                        run.assert_called_once()
                        self.assertEqual(run.call_args.args[0][:-1],
                                         ['/bin/ut', 'ed', '-c', '1'])
                        self._check_no_receipt(self.copy)

    def test_run_edit_multiple(self) -> None:
        """
        Test executing the command with (slightly different) edits in between.
        """

        with self._setup_input(self.edit, end_inputs=["e", "w"]):
            self.replaces.append(('shop: id', 'shop: other'))
            with patch("subprocess.run",
                       side_effect=self._copy_file) as copy_cmd:
                command = New()
                command.run()
                self.assertEqual(copy_cmd.call_count, 2)
                self._compare_expected_receipt(self.copy, self.expected,
                                               self.expected_products)

    def test_run_invalid(self) -> None:
        """
        Test executing the command with invalid inputs but preloaded products.
        """

        with self.database as session:
            session.add_all(deepcopy(self.products))

        with self._setup_input(Path("samples/new/invalid_input"),
                               start_inputs=[], end_inputs=["quit"]):
            command = New()
            command.run()
            self._check_no_receipt(self.create)

    def test_run_receipt_invalid(self) -> None:
        """
        Test executing the command wih some invalid inputs, a lot of product
        metadata creation, merging and editing, but still providing a valid
        receipt in the end.
        """

        with self.expected_invalid.open("w", encoding="utf-8") as expected_file:
            expected = {
                'shop': 'inv',
                'date': date(2024, 11, 1),
                'products': [
                    [1, 'bar', 0.01],
                    [2, 'xyz', 5.00, '10%'],
                    ['8oz', 'qux', 0.02, 'bonus']
                ],
                'bonus': [
                    ['rate', -0.50, 'xyz'],
                    ['disco', -0.01]
                ]
            }
            yaml.dump(expected, expected_file)

        with self._setup_input(Path("samples/new/receipt_invalid_input")):
            self.replaces.append(('sku: sp9900', 'sku: sp9999'))
            self.replaces.append(('1.00', 'oops'))
            with patch("subprocess.run", side_effect=self._edit_file) as cmd:
                command = New()
                command.confirm = True
                command.run()

                base = Product(shop='inv',
                               labels=[LabelMatch(name='bar')],
                               prices=[PriceMatch(indicator='2024',
                                                  value=Price('0.01'))],
                               description='A Bar of Chocolate',
                               portions=9,
                               sku='sp900',
                               gtin=4321987654321)
                base.range = [
                    # First range product (car)
                    # Override price matchers
                    # Received portions (staggered range merge)
                    Product(shop='inv',
                            labels=[LabelMatch(name='car')],
                            prices=[],
                            description='A Bar of Chocolate',
                            portions=9,
                            sku='sp9000'),
                    # Second range product (candy)
                    # Override of labels and price matchers
                    # Did not receive portions (later generic merge)
                    # Edited sku
                    Product(shop='inv',
                            labels=[],
                            prices=[],
                            description='A Bar of Chocolate',
                            category='candy',
                            portions=None,
                            sku='sp9999'),
                    # Same as base except no GTIN (identifiers only if explicit)
                    Product(shop='inv',
                            labels=[LabelMatch(name='bar')],
                            prices=[PriceMatch(indicator='2024',
                                               value=Price('0.01'))],
                            description='A Bar of Chocolate',
                            portions=9,
                            sku='sp900')
                ]
                matches = (base,
                           Product(shop='inv',
                                   labels=[LabelMatch(name='xyz')],
                                   discounts=[
                                       DiscountMatch(label='rate'),
                                       DiscountMatch(label='over')
                                       ],
                                   weight=Quantity('1kg')),
                           Product(shop='inv', labels=[LabelMatch(name='qux')]))
                self._compare_expected_receipt(self.create_invalid,
                                               self.expected_invalid,
                                               matches)
                self.assertEqual(cmd.call_count, 3)

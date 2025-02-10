"""
Add cascade deletes for products/discounts

Revision ID: 24c54f418b92
Revises: 
Create Date: 2025-02-07 23:15:46.360221
"""
# pylint: disable=invalid-name

from typing import Sequence, Union

from alembic import op

from rechu.database import Database
from rechu.models.receipt import Discount, DiscountItems, ProductItem

# Revision identifiers, used by Alembic.
revision: str = '24c54f418b92'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """
    Perform the upgrade.
    """

    with op.batch_alter_table('receipt_discount',
                              copy_from=Database.offline_table(Discount),
                              schema=None) as batch_op:
        receipt_discount_key = 'fk_receipt_discount_receipt_key_receipt'
        batch_op.drop_constraint(receipt_discount_key, type_='foreignkey')
        batch_op.create_foreign_key(batch_op.f(receipt_discount_key), 'receipt',
                                    ['receipt_key'], ['filename'],
                                    ondelete='CASCADE')

    with op.batch_alter_table('receipt_discount_products',
                              copy_from=Database.offline_table(DiscountItems),
                              schema=None) as batch_op:
        discount = 'fk_receipt_discount_products_discount_id_receipt_discount'
        product = 'fk_receipt_discount_products_product_id_receipt_product'
        batch_op.drop_constraint(discount, type_='foreignkey')
        batch_op.drop_constraint(product, type_='foreignkey')
        batch_op.create_foreign_key(batch_op.f(discount), 'receipt_discount',
                                    ['discount_id'], ['id'], ondelete='CASCADE')
        batch_op.create_foreign_key(batch_op.f(product), 'receipt_product',
                                    ['product_id'], ['id'], ondelete='CASCADE')

    with op.batch_alter_table('receipt_product',
                              copy_from=Database.offline_table(ProductItem),
                              schema=None) as batch_op:
        receipt_product_key = 'fk_receipt_product_receipt_key_receipt'
        batch_op.drop_constraint(receipt_product_key, type_='foreignkey')
        batch_op.create_foreign_key(batch_op.f(receipt_product_key), 'receipt',
                                    ['receipt_key'], ['filename'],
                                    ondelete='CASCADE')

    # ### end Alembic commands ###


def downgrade() -> None:
    """
    Perform the downgrade.
    """

    with op.batch_alter_table('receipt_product',
                              copy_from=Database.offline_table(ProductItem),
                              schema=None) as batch_op:
        receipt_product_key = 'fk_receipt_product_receipt_key_receipt'
        batch_op.drop_constraint(batch_op.f(receipt_product_key),
                                 type_='foreignkey')
        batch_op.create_foreign_key(receipt_product_key, 'receipt',
                                    ['receipt_key'], ['filename'])

    with op.batch_alter_table('receipt_discount_products',
                              copy_from=Database.offline_table(DiscountItems),
                              schema=None) as batch_op:
        product = 'fk_receipt_discount_products_product_id_receipt_product'
        discount = 'fk_receipt_discount_products_discount_id_receipt_discount'
        batch_op.drop_constraint(batch_op.f(product), type_='foreignkey')
        batch_op.drop_constraint(batch_op.f(discount), type_='foreignkey')
        batch_op.create_foreign_key(product, 'receipt_product',
                                    ['product_id'], ['id'])
        batch_op.create_foreign_key(discount, 'receipt_discount',
                                    ['discount_id'], ['id'])

    with op.batch_alter_table('receipt_discount',
                              copy_from=Database.offline_table(Discount),
                              schema=None) as batch_op:
        receipt_discount_key = 'fk_receipt_discount_receipt_key_receipt'
        batch_op.drop_constraint(batch_op.f(receipt_discount_key),
                                 type_='foreignkey')
        batch_op.create_foreign_key(receipt_discount_key, 'receipt',
                                    ['receipt_key'], ['filename'])

    # ### end Alembic commands ###

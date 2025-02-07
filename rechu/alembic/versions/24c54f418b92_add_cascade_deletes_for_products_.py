"""
Add cascade deletes for products/discounts

Revision ID: 24c54f418b92
Revises: 
Create Date: 2025-02-07 23:15:46.360221
"""
# pylint: disable=invalid-name, line-too-long

from typing import Sequence, Union

from alembic import op

# Revision identifiers, used by Alembic.
revision: str = '24c54f418b92'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Perform the upgrade.
    """

    with op.batch_alter_table('receipt_discount', schema=None) as batch_op:
        batch_op.drop_constraint('fk_receipt_discount_receipt_key_receipt', type_='foreignkey')
        batch_op.create_foreign_key(batch_op.f('fk_receipt_discount_receipt_key_receipt'), 'receipt', ['receipt_key'], ['filename'], ondelete='CASCADE')

    with op.batch_alter_table('receipt_discount_products', schema=None) as batch_op:
        batch_op.drop_constraint('fk_receipt_discount_products_discount_id_receipt_discount', type_='foreignkey')
        batch_op.drop_constraint('fk_receipt_discount_products_product_id_receipt_product', type_='foreignkey')
        batch_op.create_foreign_key(batch_op.f('fk_receipt_discount_products_discount_id_receipt_discount'), 'receipt_discount', ['discount_id'], ['id'], ondelete='CASCADE')
        batch_op.create_foreign_key(batch_op.f('fk_receipt_discount_products_product_id_receipt_product'), 'receipt_product', ['product_id'], ['id'], ondelete='CASCADE')

    with op.batch_alter_table('receipt_product', schema=None) as batch_op:
        batch_op.drop_constraint('fk_receipt_product_receipt_key_receipt', type_='foreignkey')
        batch_op.create_foreign_key(batch_op.f('fk_receipt_product_receipt_key_receipt'), 'receipt', ['receipt_key'], ['filename'], ondelete='CASCADE')

    # ### end Alembic commands ###


def downgrade() -> None:
    """
    Perform the downgrade.
    """

    with op.batch_alter_table('receipt_product', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_receipt_product_receipt_key_receipt'), type_='foreignkey')
        batch_op.create_foreign_key('fk_receipt_product_receipt_key_receipt', 'receipt', ['receipt_key'], ['filename'])

    with op.batch_alter_table('receipt_discount_products', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_receipt_discount_products_product_id_receipt_product'), type_='foreignkey')
        batch_op.drop_constraint(batch_op.f('fk_receipt_discount_products_discount_id_receipt_discount'), type_='foreignkey')
        batch_op.create_foreign_key('fk_receipt_discount_products_product_id_receipt_product', 'receipt_product', ['product_id'], ['id'])
        batch_op.create_foreign_key('fk_receipt_discount_products_discount_id_receipt_discount', 'receipt_discount', ['discount_id'], ['id'])

    with op.batch_alter_table('receipt_discount', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_receipt_discount_receipt_key_receipt'), type_='foreignkey')
        batch_op.create_foreign_key('fk_receipt_discount_receipt_key_receipt', 'receipt', ['receipt_key'], ['filename'])

    # ### end Alembic commands ###

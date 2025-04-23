"""
Add product relation and shop

Revision ID: d6854aeb9756
Revises: 9d5f6a8f4944
Create Date: 2025-04-23 23:21:27.451326
"""
# pylint: disable=invalid-name

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Revision identifiers, used by Alembic.
revision: str = 'd6854aeb9756'
down_revision: Union[str, None] = '9d5f6a8f4944'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Perform the upgrade.
    """

    with op.batch_alter_table('product', schema=None) as batch_op:
        batch_op.add_column(sa.Column('shop', sa.String(length=32),
                                      nullable=False))

    with op.batch_alter_table('receipt_product', schema=None) as batch_op:
        batch_op.add_column(sa.Column('product_id', sa.Integer(),
                                      nullable=True))
        receipt_product_product_key = 'fk_receipt_product_product_id_product'
        batch_op.create_foreign_key(batch_op.f(receipt_product_product_key),
                                    'product', ['product_id'], ['id'],
                                    ondelete='SET NULL')

    # ### end Alembic commands ###


def downgrade() -> None:
    """
    Perform the downgrade.
    """

    with op.batch_alter_table('receipt_product', schema=None) as batch_op:
        receipt_product_product_key = 'fk_receipt_product_product_id_product'
        batch_op.drop_constraint(batch_op.f(receipt_product_product_key),
                                 type_='foreignkey')
        batch_op.drop_column('product_id')

    with op.batch_alter_table('product', schema=None) as batch_op:
        batch_op.drop_column('shop')

    # ### end Alembic commands ###

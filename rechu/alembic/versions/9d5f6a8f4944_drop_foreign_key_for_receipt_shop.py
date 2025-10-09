"""
Drop foreign key for receipt shop

Revision ID: 9d5f6a8f4944
Revises: 24c54f418b92
Create Date: 2025-02-10 20:23:02.768133
"""
# pylint: disable=invalid-name

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import column, table

# Revision identifiers, used by Alembic.
revision: str = '9d5f6a8f4944'
down_revision: Union[str, None] = '24c54f418b92'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Perform the upgrade.
    """

    with op.batch_alter_table('receipt', schema=None) as batch_op:
        batch_op.drop_constraint('fk_receipt_shop_shop', type_='foreignkey')

    # ### end Alembic commands ###


def downgrade() -> None:
    """
    Perform the downgrade.
    """

    with op.batch_alter_table('receipt', schema=None) as batch_op:
        receipt = table('receipt', column('shop', sa.String(32)))
        shop = table('shop', column('key', sa.String(32)))
        key = receipt.c.shop.label("key")
        exist = shop.c.key.label("exist")
        select = sa.select(key).join(shop, exist == key, isouter=True) \
            .filter(exist.is_(None)).distinct()
        batch_op.execute(shop.insert().from_select(["key"], select))
        batch_op.create_foreign_key('fk_receipt_shop_shop', 'shop', ['shop'],
                                    ['key'])

    # ### end Alembic commands ###

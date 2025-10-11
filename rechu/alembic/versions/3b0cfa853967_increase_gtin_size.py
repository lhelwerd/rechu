"""
Increase GTIN size

Revision ID: 3b0cfa853967
Revises: aaff17ed83d8
Create Date: 2025-04-26 21:27:07.365156
"""
# pylint: disable=invalid-name

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import column, table


# Revision identifiers, used by Alembic.
revision: str = "3b0cfa853967"
down_revision: Union[str, None] = "aaff17ed83d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Perform the upgrade.
    """

    with op.batch_alter_table("product", schema=None) as batch_op:
        batch_op.alter_column(
            "gtin",
            existing_type=sa.INTEGER(),
            type_=sa.BigInteger(),
            existing_nullable=True,
        )

    # ### end Alembic commands ###


def downgrade() -> None:
    """
    Perform the downgrade.
    """

    with op.batch_alter_table("product", schema=None) as batch_op:
        product = table(
            "product",
            column("id", sa.Integer()),
            column("gtin", sa.BigInteger()),
        )
        batch_op.execute(product.update().values(gtin=None))
        batch_op.alter_column(
            "gtin",
            existing_type=sa.BigInteger(),
            type_=sa.INTEGER(),
            existing_nullable=True,
        )

    # ### end Alembic commands ###

"""
Add receipt item position fields

Revision ID: b1a7a91c8de8
Revises: 3b0cfa853967
Create Date: 2025-05-08 23:06:02.101619
"""
# pylint: disable=invalid-name

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql import column, table

# Revision identifiers, used by Alembic.
revision: str = "b1a7a91c8de8"
down_revision: str | None = "3b0cfa853967"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Perform the upgrade.
    """

    with op.batch_alter_table("receipt_discount", schema=None) as batch_op:
        batch_op.add_column(sa.Column("position", sa.Integer(), nullable=True))
        discount = table(
            "receipt_discount",
            column("id", sa.Integer()),
            column("position", sa.Integer()),
        )
    with op.batch_alter_table("receipt_discount", schema=None) as batch_op:
        batch_op.execute(discount.update().values(position=discount.c.id))
        batch_op.alter_column(
            "position",
            existing_type=sa.Integer(),
            existing_nullable=True,
            nullable=False,
        )

    with op.batch_alter_table("receipt_product", schema=None) as batch_op:
        batch_op.add_column(sa.Column("position", sa.Integer(), nullable=True))
        product = table(
            "receipt_product",
            column("id", sa.Integer()),
            column("position", sa.Integer()),
        )
    with op.batch_alter_table("receipt_product", schema=None) as batch_op:
        batch_op.execute(product.update().values(position=product.c.id))
        batch_op.alter_column(
            "position",
            existing_type=sa.Integer(),
            existing_nullable=True,
            nullable=False,
        )

    # ### end Alembic commands ###


def downgrade() -> None:
    """
    Perform the downgrade.
    """

    with op.batch_alter_table("receipt_product", schema=None) as batch_op:
        batch_op.drop_column("position")

    with op.batch_alter_table("receipt_discount", schema=None) as batch_op:
        batch_op.drop_column("position")

    # ### end Alembic commands ###

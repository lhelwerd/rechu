"""
Add shop metadata and foreign key

Revision ID: 81b6d004d3c5
Revises: 5a5bf02e8988
Create Date: 2025-08-28 22:33:27.840209
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Revision identifiers, used by Alembic.
revision: str = "81b6d004d3c5"
down_revision: str | None = "5a5bf02e8988"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Perform the upgrade.
    """

    indicator_pk = "pk_shop_discount_indicator"
    indicator_fk = "fk_shop_discount_indicator_shop_id_shop"
    _ = op.create_table(
        "shop_discount_indicator",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("shop_id", sa.String(length=32), nullable=False),
        sa.Column("pattern", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["shop_id"],
            ["shop.key"],
            name=op.f(indicator_fk),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f(indicator_pk)),
    )
    with op.batch_alter_table("product", schema=None) as batch_op:
        batch_op.create_foreign_key(
            batch_op.f("fk_product_shop_shop"), "shop", ["shop"], ["key"]
        )

    with op.batch_alter_table("receipt", schema=None) as batch_op:
        batch_op.create_foreign_key(
            batch_op.f("fk_receipt_shop_shop"), "shop", ["shop"], ["key"]
        )

    with op.batch_alter_table("shop", schema=None) as batch_op:
        batch_op.add_column(sa.Column("products", sa.String(), nullable=True))


def downgrade() -> None:
    """
    Perform the downgrade.
    """

    with op.batch_alter_table("shop", schema=None) as batch_op:
        batch_op.drop_column("products")

    with op.batch_alter_table("receipt", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_receipt_shop_shop"), type_="foreignkey"
        )

    with op.batch_alter_table("product", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_product_shop_shop"), type_="foreignkey"
        )

    op.drop_table("shop_discount_indicator")

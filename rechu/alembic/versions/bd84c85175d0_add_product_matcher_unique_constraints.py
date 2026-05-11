"""
Add product matcher unique constraints

Revision ID: bd84c85175d0
Revises: 720350314f42
Create Date: 2026-04-26 17:18:48.331994
"""
# pylint: disable=invalid-name, line-too-long

from collections.abc import Sequence

from alembic import op

# Revision identifiers, used by Alembic.
revision: str = "bd84c85175d0"
down_revision: str | None = "720350314f42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Perform the upgrade.
    """

    with op.batch_alter_table(
        "product_discount_match", schema=None
    ) as batch_op:
        batch_op.create_unique_constraint(
            batch_op.f("uq_product_discount_match_product_id"),
            ["product_id", "label"],
        )

    with op.batch_alter_table("product_label_match", schema=None) as batch_op:
        batch_op.create_unique_constraint(
            batch_op.f("uq_product_label_match_product_id"),
            ["product_id", "name"],
        )

    with op.batch_alter_table("product_price_match", schema=None) as batch_op:
        batch_op.create_unique_constraint(
            batch_op.f("uq_product_price_match_product_id"),
            ["product_id", "indicator"],
        )


def downgrade() -> None:
    """
    Perform the downgrade.
    """

    with op.batch_alter_table("product_price_match", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("uq_product_price_match_product_id"), type_="unique"
        )

    with op.batch_alter_table("product_label_match", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("uq_product_label_match_product_id"), type_="unique"
        )

    with op.batch_alter_table(
        "product_discount_match", schema=None
    ) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("uq_product_discount_match_product_id"), type_="unique"
        )

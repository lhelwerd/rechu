"""
Add product matchers

Revision ID: aaff17ed83d8
Revises: d6854aeb9756
Create Date: 2025-04-25 18:08:04.816341
"""
# pylint: disable=invalid-name

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


# Revision identifiers, used by Alembic.
revision: str = "aaff17ed83d8"
down_revision: Union[str, None] = "d6854aeb9756"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Perform the upgrade.
    """

    product_ref = "product.id"

    discount_fk = "fk_product_discount_match_product_id_product"
    discount_pk = "pk_product_discount_match"
    _ = op.create_table(
        "product_discount_match",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["product_id"],
            [product_ref],
            name=op.f(discount_fk),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f(discount_pk)),
    )

    label_fk = "fk_product_label_match_product_id_product"
    label_pk = "pk_product_label_match"
    _ = op.create_table(
        "product_label_match",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["product_id"],
            [product_ref],
            name=op.f(label_fk),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f(label_pk)),
    )

    price_fk = "fk_product_price_match_product_id_product"
    price_pk = "pk_product_price_match"
    _ = op.create_table(
        "product_price_match",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("value", sa.Numeric(scale=2), nullable=False),
        sa.Column("indicator", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["product_id"],
            [product_ref],
            name=op.f(price_fk),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f(price_pk)),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    """
    Perform the downgrade.
    """

    op.drop_table("product_price_match")
    op.drop_table("product_label_match")
    op.drop_table("product_discount_match")
    # ### end Alembic commands ###

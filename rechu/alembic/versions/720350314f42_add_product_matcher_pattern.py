"""
Add product matcher pattern

Revision ID: 720350314f42
Revises: 81b6d004d3c5
Create Date: 2026-01-18 00:33:56.032167
"""
# pylint: disable=invalid-name

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Revision identifiers, used by Alembic.
revision: str = "720350314f42"
down_revision: str | None = "81b6d004d3c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Perform the upgrade.
    """

    with op.batch_alter_table(
        "product_discount_match", schema=None
    ) as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_pattern",
                sa.Boolean(),
                server_default=sa.false(),
                nullable=False,
            )
        )

    with op.batch_alter_table("product_label_match", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_pattern",
                sa.Boolean(),
                server_default=sa.false(),
                nullable=False,
            )
        )


def downgrade() -> None:
    """
    Perform the downgrade.
    """

    with op.batch_alter_table("product_label_match", schema=None) as batch_op:
        batch_op.drop_column("is_pattern")

    with op.batch_alter_table(
        "product_discount_match", schema=None
    ) as batch_op:
        batch_op.drop_column("is_pattern")

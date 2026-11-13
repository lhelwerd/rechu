"""
Convert product amount float to double

Revision ID: 26ac04e451b8
Revises: bd84c85175d0
Create Date: 2026-11-09 22:35:27.365305
"""
# pylint: disable=invalid-name, line-too-long

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Revision identifiers, used by Alembic.
revision: str = "26ac04e451b8"
down_revision: str | None = "bd84c85175d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Perform the upgrade.
    """

    with op.batch_alter_table("receipt_product", schema=None) as batch_op:
        batch_op.alter_column(
            "amount",
            existing_type=sa.FLOAT(),
            type_=sa.Double(),
            existing_nullable=False,
        )


def downgrade() -> None:
    """
    Perform the downgrade.
    """

    with op.batch_alter_table("receipt_product", schema=None) as batch_op:
        batch_op.alter_column(
            "amount",
            existing_type=sa.Double(),
            type_=sa.FLOAT(),
            existing_nullable=False,
        )

"""
Add receipt item extracted quantity fields

Revision ID: 8ef12eb24650
Revises: b1a7a91c8de8
Create Date: 2025-05-29 22:55:58.519845
"""
# pylint: disable=invalid-name

from collections.abc import Iterator, Sequence
from typing import Union, cast

from alembic import context, op
from alembic.operations import BatchOperations
import sqlalchemy as sa
from sqlalchemy.sql import TableClause, table, column
from rechu.database import Database
from rechu.models.base import Quantity

# Revision identifiers, used by Alembic.
revision: str = "8ef12eb24650"
down_revision: Union[str, None] = "b1a7a91c8de8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

Amounts = list[dict[str, Union[float, str]]]
Units = list[dict[str, Union[int, str]]]


def upgrade() -> None:
    """
    Perform the upgrade.
    """

    product = table(
        "receipt_product",
        column("id", sa.Integer()),
        column("quantity", sa.String()),
        column("amount", sa.Float()),
        column("unit", sa.String()),
    )
    amounts, units = collect_quantity(product)

    with op.batch_alter_table("receipt_product", schema=None) as batch_op:
        batch_op.add_column(sa.Column("amount", sa.Float(), nullable=True))

    with op.batch_alter_table("receipt_product", schema=None) as batch_op:
        update_amount(batch_op, product, amounts)

    with op.batch_alter_table("receipt_product", schema=None) as batch_op:
        batch_op.alter_column(
            "amount",
            existing_type=sa.Float(),
            existing_nullable=True,
            nullable=False,
        )
        batch_op.add_column(sa.Column("unit", sa.String(), nullable=True))

    with op.batch_alter_table("receipt_product", schema=None) as batch_op:
        update_unit(batch_op, product, units)

    # ### end Alembic commands ###


class ProductQuantityRow(sa.Row[tuple[int, Quantity]]):
    """
    Result row of query of existing product quantities.
    """

    id: int
    quantity: Quantity


def collect_quantity(product: TableClause) -> tuple[Amounts, Units]:
    """
    Extract quantity fields.
    """

    amounts: Amounts = []
    units: Units = []
    with Database() as session:
        if context.is_offline_mode():
            connection = session.connection()
        else:
            connection = op.get_bind()
        results = cast(
            Iterator[ProductQuantityRow],
            iter(
                connection.execute(sa.select(product.c.id, product.c.quantity))
            ),
        )
        for row in results:
            quantity = Quantity(row.quantity)
            amounts.append({"row_id": row.id, "amount": quantity.amount})
            if quantity.unit is not None:
                units.append({"row_id": row.id, "unit": str(quantity.unit)})

    return amounts, units


def update_amount(
    batch_op: BatchOperations, product: TableClause, amounts: Amounts
) -> None:
    """
    Update the amount column.
    """

    for amount in amounts:
        batch_op.execute(
            product.update()
            .where(product.c.id == amount["row_id"])
            .values({"amount": amount["amount"]})
        )


def update_unit(
    batch_op: BatchOperations, product: TableClause, units: Units
) -> None:
    """
    Update the unit column.
    """

    for unit in units:
        batch_op.execute(
            product.update()
            .where(product.c.id == unit["row_id"])
            .values({"unit": unit["unit"]})
        )


def downgrade() -> None:
    """
    Perform the downgrade.
    """

    with op.batch_alter_table("receipt_product", schema=None) as batch_op:
        batch_op.drop_column("unit")
        batch_op.drop_column("amount")

    # ### end Alembic commands ###

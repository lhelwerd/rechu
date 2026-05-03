"""
Base model for receipt cataloging.
"""

from typing import ClassVar, Literal

from sqlalchemy import Connection, MetaData, event
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapper,
    QueryContext,
    registry as RegistryType,
)
from sqlalchemy.orm.decl_api import DeclarativeAttributeIntercept

from ..types.measurable import (
    Quantity as Quantity,
    QuantityType,
    Unit as Unit,
    UnitType,
)
from ..types.quantized import GTIN as GTIN, GTINType, Price as Price, PriceType


class Base(DeclarativeBase, metaclass=DeclarativeAttributeIntercept):
    # pylint: disable=too-few-public-methods
    """
    Base ORM model class for receipt models.
    """

    metadata: ClassVar[MetaData] = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )

    registry: ClassVar[RegistryType] = RegistryType(
        type_annotation_map={
            Price: PriceType,
            Quantity: QuantityType,
            Unit: UnitType,
            GTIN: GTINType,
        }
    )

    origin: Literal["db", "external"] = "external"


@event.listens_for(Base, "load", propagate=True, restore_load_context=True)
def receive_load(target: Base, _context: QueryContext) -> None:
    """
    Register that the model was loaded from the database.
    """

    target.origin = "db"


@event.listens_for(Base, "after_insert", propagate=True)
def receive_after_insert(
    _mapper: Mapper[Base], _connection: Connection, target: Base
) -> None:
    """
    Register that the model was added to the database.
    """

    target.origin = "db"

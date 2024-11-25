"""
Base model for receipt cataloging.
"""

from decimal import Decimal
from typing import Annotated
from sqlalchemy import MetaData, Numeric
from sqlalchemy.orm import DeclarativeBase, registry

# Price type with scale of 2 (number of decimal places)
Price = Annotated[Decimal, 2]

class Base(DeclarativeBase): # pylint: disable=too-few-public-methods
    """
    Base ORM model class for receipt models.
    """

    metadata = MetaData(naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    })

    registry = registry(type_annotation_map={Price: Numeric(None, 2)})

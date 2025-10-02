"""
Tests for receipt cataloging module.
"""

from collections.abc import Callable
from typing import Any, TypeVar

CT = TypeVar("CT", bound=Callable[..., Any])

def concrete(method: CT) -> CT:
    """
    Make an abstract method of an class extending from `ABC` non-abstract such
    that the class may be instantiated.
    """

    setattr(method, "__isabstractmethod__", False)
    return method

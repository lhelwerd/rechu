"""
Submodule for inventory of grouped models.
"""

from .base import Inventory
from .products import Products
from .shops import Shops

__all__ = ["Inventory", "Products", "Shops"]

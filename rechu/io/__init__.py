"""
Models for file reading and writing.
"""

from .products import ProductsReader, ProductsWriter
from .receipt import ReceiptReader, ReceiptWriter
from .shops import ShopsReader, ShopsWriter

__all__ = [
    "ProductsReader",
    "ProductsWriter",
    "ReceiptReader",
    "ReceiptWriter",
    "ShopsReader",
    "ShopsWriter",
]

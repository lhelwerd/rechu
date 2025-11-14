"""
Quit step of new subcommand.
"""

import logging
from dataclasses import dataclass

from typing_extensions import override

from .base import ResultMeta, Step

LOGGER = logging.getLogger(__name__)


@dataclass
class Quit(Step):
    """
    Step to exit the receipt creation menu.
    """

    @override
    def run(self) -> ResultMeta:
        LOGGER.warning("Discarding entire receipt")
        return {}

    @property
    @override
    def description(self) -> str:
        return "Exit the receipt creation menu without writing"

    @property
    @override
    def final(self) -> bool:
        return True

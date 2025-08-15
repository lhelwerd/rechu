"""
Quit step of new subcommand.
"""

import logging
from .base import ResultMeta, Step

LOGGER = logging.getLogger(__name__)

class Quit(Step):
    """
    Step to exit the receipt creation menu.
    """

    def run(self) -> ResultMeta:
        LOGGER.warning('Discarding entire receipt')
        return {}

    @property
    def description(self) -> str:
        return "Exit the receipt creation menu without writing"

    @property
    def final(self) -> bool:
        return True

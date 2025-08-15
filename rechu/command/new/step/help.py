"""
Help step of new subcommand.
"""

from .base import Menu, ResultMeta, Step
from ..input import InputSource
from ....models.receipt import Receipt

class Help(Step):
    """
    Step to display help for steps that are usable from the menu.
    """

    def __init__(self, receipt: Receipt, input_source: InputSource):
        super().__init__(receipt, input_source)
        self.menu: Menu = {}

    @property
    def description(self) -> str:
        return "View this usage help message"

    def run(self) -> ResultMeta:
        output = self._input.get_output()
        choice_length = len(max(self.menu, key=len))
        for choice, step in self.menu.items():
            print(f"{choice: <{choice_length}} {step.description}", file=output)

        print("Initial characters match the first option with that prefix.",
              file=output)
        return {}

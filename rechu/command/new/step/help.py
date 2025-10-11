"""
Help step of new subcommand.
"""

from dataclasses import dataclass, field
from typing_extensions import override
from .base import Menu, ResultMeta, Step


@dataclass
class Help(Step):
    """
    Step to display help for steps that are usable from the menu.
    """

    menu: Menu = field(default_factory=dict)

    @property
    @override
    def description(self) -> str:
        return "View this usage help message"

    @override
    def run(self) -> ResultMeta:
        output = self.input.get_output()
        choice_length = len(max(self.menu, key=len))
        for choice, step in self.menu.items():
            print(f"{choice: <{choice_length}} {step.description}", file=output)

        print(
            "Initial characters match the first option with that prefix.",
            file=output,
        )
        return {}

"""
Tests for steps to create a receipt in new subcommand.
"""

from typing import final
import unittest
from typing_extensions import override
from rechu.command.new.input import Prompt
from rechu.command.new.step import Step
from rechu.models.receipt import Receipt
from ... import concrete

@final
class TestStep(Step):
    """
    Test step.
    """

    run = concrete(Step.run)
    @property
    @override
    def description(self):
        return super().description

# mypy: disable-error-code="abstract"
@final
class StepTest(unittest.TestCase):
    """
    Tests for abstract base class of a receipt creation step.
    """

    @override
    def setUp(self) -> None:
        self.step = TestStep(Receipt(), Prompt())

    def test_run(self):
        """
        Test performing the step.
        """

        with self.assertRaises(NotImplementedError):
            self.assertIsNone(self.step.run())

    def test_description(self):
        """
        Test retreiving a usage message of the step.
        """

        with self.assertRaises(NotImplementedError):
            self.assertEqual(self.step.description, "")

"""
Tests for steps to create a receipt in new subcommand.
"""

import unittest
from rechu.command.new import Prompt, Step
from rechu.models.receipt import Receipt
from ... import concrete

class TestStep(Step):
    """
    Test step.
    """

    run = concrete(Step.run)
    @property
    def description(self):
        return super().description

# mypy: disable-error-code="abstract"
class StepTest(unittest.TestCase):
    """
    Tests for abstract base class of a receipt creation step.
    """

    def setUp(self) -> None:
        self.step = TestStep(Receipt(), Prompt())

    def test_run(self):
        """
        Test performing the step.
        """

        with self.assertRaises(NotImplementedError):
            self.step.run()

    def test_description(self):
        """
        Test retreiving a usage message of the step.
        """

        with self.assertRaises(NotImplementedError):
            self.assertEqual(self.step.description, "")

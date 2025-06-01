"""
Tests for steps to create a receipt in new subcommand.
"""

import unittest
from rechu.command.new import Prompt, Step
from rechu.models.receipt import Receipt

class StepTest(unittest.TestCase):
    """
    Tests for abstract base class of a receipt creation step.
    """

    def test_run(self):
        """
        Test performing the step.
        """

        with self.assertRaises(NotImplementedError):
            Step(Receipt(), Prompt()).run()

    def test_description(self):
        """
        Test retreiving a usage message of the step.
        """

        with self.assertRaises(NotImplementedError):
            self.assertEqual(Step(Receipt(), Prompt()).description, "")

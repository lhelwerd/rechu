"""
Tests for receipt subcommand base.
"""

import unittest
from rechu.command.base import Base

@Base.register("test")
class TestCommand(Base):
    """
    Example subcommand.
    """

    def run(self) -> None:
        pass

class BaseTest(unittest.TestCase):
    """
    Tests for abstract command handling.
    """

    def test_get_command(self) -> None:
        """
        Test creating a command instance.
        """

        test = Base.get_command("test")
        self.assertIsInstance(test, TestCommand)

    def test_run(self) -> None:
        """
        Test executing a command.
        """

        base = Base()
        with self.assertRaises(NotImplementedError):
            base.run()

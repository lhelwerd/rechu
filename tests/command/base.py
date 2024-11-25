"""
Tests for receipt subcommand base.
"""

from rechu.command.base import Base
from ..settings import SettingsTestCase

@Base.register("test")
class TestCommand(Base):
    """
    Example subcommand.
    """

    def run(self) -> None:
        pass

class BaseTest(SettingsTestCase):
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

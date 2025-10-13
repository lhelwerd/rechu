"""
Command entry point.
"""

import sys
from .command.base import Base


def main() -> None:
    """
    Main entry point for receipt subcommands.
    """

    Base.start(sys.executable, sys.argv)


if __name__ == "__main__":
    main()

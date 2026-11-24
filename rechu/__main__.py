"""
Command entry point.
"""

import sys

from .command.base import Base


def main() -> int:
    """
    Main entry point for receipt subcommands.
    """

    return Base.start(sys.executable, sys.argv)


if __name__ == "__main__":
    sys.exit(main())

"""
Command entry point.
"""

import sys
from .command.base import Base

def main() -> None:
    """
    Main entry point for receipt subcommands.
    """

    if len(sys.argv) <= 1:
        raise RuntimeError('Usage: python -m rechu <command>')

    name = sys.argv[1]

    command = Base.get_command(name)
    command.run()

if __name__ == "__main__":
    main()

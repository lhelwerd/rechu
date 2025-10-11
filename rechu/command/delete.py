"""
Subcommand to remove receipt YAML file(s) from data path and database.
"""

from pathlib import Path
from typing import ClassVar, final
from typing_extensions import override
from sqlalchemy import delete
from .base import Base, SubparserArguments, SubparserKeywords
from ..database import Database
from ..models import Receipt


@final
@Base.register("delete")
class Delete(Base):
    """
    Delete YAML files and database entries for receipts.
    """

    subparser_keywords: ClassVar[SubparserKeywords] = {
        "aliases": ["rm"],
        "help": "Delete receipt files and/or database entries",
        "description": (
            "Delete receipts from the YAML data paths and from the database."
        ),
    }
    subparser_arguments: ClassVar[SubparserArguments] = [
        (
            "files",
            {
                "metavar": "FILE",
                "nargs": "+",
                "help": "One or more files to delete",
            },
        ),
        (
            ("-k", "--keep"),
            {
                "action": "store_true",
                "default": False,
                "help": "Do not delete YAML file from data path",
            },
        ),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.files: list[str] = []
        self.keep = False

    @override
    def run(self) -> None:
        data_path = Path(self.settings.get("data", "path"))
        data_pattern = self.settings.get("data", "pattern")

        # Filter off path elements to just keep the file name
        files = tuple(Path(file).name for file in self.files)

        with Database() as session:
            _ = session.execute(
                delete(Receipt).where(Receipt.filename.in_(files))
            )

        if not self.keep:
            for file in files:
                self._delete(data_path, f"{data_pattern}/{file}")

    def _delete(self, data_path: Path, pattern: str) -> None:
        try:
            next(data_path.glob(pattern)).unlink()
        except (StopIteration, FileNotFoundError):
            self.logger.warning("File not found in data path: %s", pattern)

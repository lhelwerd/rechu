"""
Subcommand to remove receipt YAML file(s) from data path and database.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from sqlalchemy import delete
from typing_extensions import override

from ..database import Database
from ..models import Receipt
from .base import Base, SubparserArguments, SubparserKeywords


@dataclass
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
        (
            ("-f", "--force"),
            {
                "action": "store_true",
                "default": False,
                "help": "Ignore errors in removing files",
            },
        ),
    ]

    files: list[str] = field(default_factory=list)
    keep: bool = False
    force: bool = False

    @override
    def run(self) -> int:
        data_path = Path(self.settings.get("data", "path"))
        data_pattern = self.settings.get("data", "pattern")

        # Filter off path elements to just keep the file name
        files = tuple(Path(file).name for file in self.files)

        with Database() as session:
            db_count = len(
                session.execute(
                    delete(Receipt)
                    .where(Receipt.filename.in_(files))
                    .returning(Receipt.filename)
                )
                .scalars()
                .all()
            )
            self.logger.info("Removed %d receipts from database", db_count)

        if not self.keep:
            file_count = 0
            for file in files:
                file_count += int(
                    self._delete(data_path, f"{data_pattern}/{file}")
                )

            self.logger.info("Removed %d files from data path", file_count)
            if not self.force and (file_count == 0 or file_count != db_count):
                return 1

        return 0

    def _delete(self, data_path: Path, pattern: str) -> bool:
        try:
            next(data_path.glob(pattern)).unlink()
        except (StopIteration, FileNotFoundError):
            self.logger.warning("File not found in data path: %s", pattern)
            return False

        return True

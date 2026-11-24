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
        files = {Path(file).name for file in self.files}
        status = 0

        with Database() as session:
            db_files = set(
                session.execute(
                    delete(Receipt)
                    .where(Receipt.filename.in_(files))
                    .returning(Receipt.filename)
                ).scalars()
            )
            self.logger.info("Removed %d receipts from database", len(db_files))
            if not self.force and db_files != files:
                self.logger.warning(
                    "Did not delete some files from database: %r",
                    files - db_files,
                )
                status = 1

        if not self.keep:
            data_files: set[str] = set()
            for file in files:
                if self._delete(data_path, f"{data_pattern}/{file}"):
                    data_files.add(file)

            self.logger.info("Removed %d files from data path", len(data_files))
            if not self.force and (not data_files or data_files != files):
                self.logger.warning(
                    "Did not delete some files from data path: %r",
                    files - data_files,
                )
                status = 1

        return status

    def _delete(self, data_path: Path, pattern: str) -> bool:
        try:
            next(data_path.glob(pattern)).unlink()
        except (StopIteration, FileNotFoundError):
            if not self.force:
                self.logger.warning("File not found in data path: %s", pattern)
            return False

        return True

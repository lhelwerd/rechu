"""
Subcommand to export database entries as YAML files.
"""

from pathlib import Path
from sqlalchemy import select
from .base import Base
from ..database import Database
from ..io.receipt import ReceiptWriter
from ..models.receipt import Receipt

@Base.register("dump")
class Dump(Base):
    """
    Dump YAML files from the database.
    """

    subparser_keywords = {
        'help': 'Export entities from the database',
        'description': 'Create one or more YAML files for data in the database.'
    }
    subparser_arguments = [
        ('files', {
            'metavar': 'FILE',
            'nargs': '*',
            'help': 'One or more receipts to write; if none are provided, then '
                    'the entire database is dumped'
        })
    ]

    def __init__(self) -> None:
        super().__init__()
        self.files: list[str] = []

    def run(self) -> None:
        data_path = Path(self.settings.get('data', 'path'))
        data_format = self.settings.get('data', 'format')

        # Filter off path elements to just keep the file name
        files = tuple(Path(file).name for file in self.files)

        directories: set[Path] = set()
        with Database() as session:
            receipts = select(Receipt)
            if files:
                receipts = receipts.where(Receipt.filename.in_(files))
            for receipt in session.scalars(receipts):
                path_format = data_path / data_format.format(date=receipt.date,
                                                             shop=receipt.shop)
                path = path_format.parent / receipt.filename
                # Only write new files, do not overwrite existing ones
                if not path.exists():
                    if path.parent not in directories:
                        # Create directories when needed, cache directories
                        path.parent.mkdir(parents=True, exist_ok=True)
                        directories.add(path.parent)

                    writer = ReceiptWriter(path, (receipt,))
                    writer.write()

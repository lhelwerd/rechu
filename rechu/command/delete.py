"""
Subcommand to remove receipt YAML file(s) from data path and database.
"""

from pathlib import Path
from sqlalchemy import delete
from .base import Base
from ..database import Database
from ..models import Receipt

@Base.register("delete")
class Delete(Base):
    """
    Delete YAML files and database entries for receipts.
    """

    subparser_keywords = {
        'aliases': ['rm'],
        'help': 'Delete receipt files and/or database entries',
        'description': 'Delete YAML files for receipts from the data paths and '
                       'from the database.'
    }
    subparser_arguments = [
        ('files', {
            'metavar': 'FILE',
            'nargs': '+',
            'help': 'One or more files to delete'
        }),
        (('-k', '--keep'), {
            'action': 'store_true',
            'default': False,
            'help': 'Do not delete YAML file from data path'
        })
    ]

    def __init__(self) -> None:
        super().__init__()
        self.files: list[str] = []
        self.keep = False

    def run(self) -> None:
        data_path = Path(self.settings.get('data', 'path'))
        data_pattern = self.settings.get('data', 'pattern')

        # Filter off path elements to just keep the file name
        files = tuple(Path(file).name for file in self.files)

        with Database() as session:
            session.execute(delete(Receipt).where(Receipt.filename.in_(files)))

        if not self.keep:
            for file in files:
                try:
                    next(data_path.glob(f"{data_pattern}/{file}")).unlink()
                except (StopIteration, FileNotFoundError):
                    self.logger.warning("File not found in data path: %s", file)

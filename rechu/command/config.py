"""
Subcommand to generate an amalgamate settings file.
"""

from .base import Base
from ..settings import Settings

@Base.register("config")
class Config(Base):
    """
    Obtain settings file representation.
    """

    subparser_keywords = {
        'help': 'Obtain settings representation',
        'description': 'Generate settings TOML representation with comments.'
    }
    subparser_arguments = [
        (('section',), {
            'metavar': 'KEY',
            'nargs': '?',
            'help': 'Optional section to filter on'
        }),
        (('key',), {
            'metavar': 'KEY',
            'nargs': '?',
            'help': 'Optional settings key to filter on'
        }),
        (('-f', '--file'), {
            'help': 'Generate based on specific TOML file'
        }),
        (('-p', '--prefix'), {
            'nargs': '+',
            'help': 'Section prefixes in specific TOML file to look up'
        })
    ]

    def __init__(self) -> None:
        super().__init__()
        self.section: str = ''
        self.key: str = ''
        self.file: str = ''
        self.prefix: tuple[str] = ()

    def run(self) -> None:
        if self.file:
            document = Settings(path=self.file, environment=False,
                                prefix=self.prefix)
        else:
            document = self.settings.get_document()

        if self.section:
            document = document[self.section]
            if self.key:
                document = document[self.key]

        print(document.as_string())

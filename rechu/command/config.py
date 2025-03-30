"""
Subcommand to generate an amalgamate settings file.
"""

from tomlkit.container import Container
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
            'metavar': 'SECTION',
            'nargs': '?',
            'help': 'Optional table section name to filter on'
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
            'default': (),
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
                                prefix=self.prefix).get_document()
        else:
            document = self.settings.get_document()

        if self.section:
            table = document[self.section]
            table.trivia.indent = ''
            container = Container()
            if self.key:
                comments = self.settings.get_comments()
                item = Container()
                for comment in comments.get(self.section, {}).get(self.key, []):
                    item.add(comment)
                item[self.key] = table[self.key]
                table = item

            container[self.section] = table

            document = container

        print(document.as_string())

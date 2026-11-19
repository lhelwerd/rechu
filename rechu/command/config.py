"""
Subcommand to generate an amalgamate settings file.
"""

from dataclasses import dataclass
from typing import ClassVar, cast

import tomlkit
from tomlkit.container import Container
from tomlkit.items import Item, Table
from typing_extensions import override

from ..settings import Settings
from .base import Base, SubparserArguments, SubparserKeywords

_Item = Item | Container


@dataclass
@Base.register("config")
class Config(Base):
    """
    Obtain settings file representation.
    """

    subparser_keywords: ClassVar[SubparserKeywords] = {
        "help": "Obtain settings representation",
        "description": "Generate settings TOML representation with comments.",
    }
    subparser_arguments: ClassVar[SubparserArguments] = [
        (
            ("section",),
            {
                "metavar": "SECTION",
                "nargs": "?",
                "help": "Optional table section name to filter on",
            },
        ),
        (
            ("key",),
            {
                "metavar": "KEY",
                "nargs": "?",
                "help": "Optional settings key to filter on",
            },
        ),
        (("-f", "--file"), {"help": "Generate based on specific TOML file"}),
        (
            ("-p", "--prefix"),
            {
                "nargs": "+",
                "default": (),
                "help": "Section prefixes in specific TOML file to look up",
            },
        ),
    ]

    section: str = ""
    key: str = ""
    file: str = ""
    prefix: tuple[str, ...] = ()

    @override
    def run(self) -> int:
        output, code = self._locate_config()
        print(output)
        return code

    def _locate_config(self) -> tuple[str, int]:
        if self.file:
            document = Settings(
                path=self.file, environment=False, prefix=self.prefix
            ).get_document()
        else:
            document = self.settings.get_document()

        code = 0
        match self.section:
            case "":
                # No section provided, return full document
                output = document.as_string()
            case section if section in document:
                table = cast(_Item, document[self.section])
                container = tomlkit.table()
                if isinstance(table, Table):
                    table.trivia.indent = ""
                    if self.key:
                        if self.key not in table:
                            return "", 1

                        table = self._wrap_setting(
                            cast(_Item, table[self.key]), self.key
                        )

                    container[self.section] = table
                else:
                    code = 1

                output = container.as_string()
            case _:
                # Section not in document
                return "", 1

        return output, code

    def _wrap_setting(self, item: _Item, key: str) -> Table:
        comments = self.settings.get_comments()
        table = tomlkit.table()
        for comment in comments.get(self.section, {}).get(key, []):
            _ = table.add(tomlkit.comment(comment))
        table[key] = item
        return table

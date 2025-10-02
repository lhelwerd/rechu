"""
Settings module.
"""

import os
from pathlib import Path
from typing import Union
import tomlkit
from tomlkit.container import Container, OutOfOrderTableProxy
from tomlkit.items import Comment, Item, Table
from typing_extensions import Required, TypedDict

class _SettingsFile(TypedDict, total=False):
    path: Required[Union[str, os.PathLike[str]]]
    environment: bool
    prefix: tuple[str, ...]

_Chain = tuple[_SettingsFile, ...]
_Section = Union[Table, tomlkit.TOMLDocument]
_SectionComments = dict[str, list[str]]
_DocumentComments = dict[str, _SectionComments]

SETTINGS_FILE_NAME = 'settings.toml'

class Settings:
    """
    Settings reader and provider.
    """

    FILES: _Chain = (
        {
            'path': SETTINGS_FILE_NAME
        },
        {
            'path': 'pyproject.toml',
            'environment': False,
            'prefix': ('tool', 'rechu')
        },
        {
            'path': Path(__file__).parent / SETTINGS_FILE_NAME,
            'environment': False
        }
    )
    _files: dict[int, "Settings"] = {}

    @classmethod
    def get_settings(cls) -> "Settings":
        """
        Retrieve the settings singleton.
        """

        return cls._get_fallback(cls.FILES)

    @classmethod
    def _get_fallback(cls, fallbacks: _Chain) -> "Settings":
        key = hash(tuple(tuple(file.values()) for file in fallbacks))
        if key not in cls._files:
            cls._files[key] = cls(fallbacks=fallbacks[1:], **fallbacks[0])

        return cls._files[key]

    @classmethod
    def clear(cls) -> None:
        """
        Remove the singleton instance and any fallback instances.
        """

        cls._files = {}

    @staticmethod
    def _traverse(table: _Section, prefix: tuple[str, ...]) -> _Section:
        for group in prefix:
            if group not in table:
                return tomlkit.table()

            item = table[group]
            if isinstance(item, (Table, OutOfOrderTableProxy)):
                table = item
            else:
                raise TypeError(f"Expected table while traversing {group} of "
                                f"{prefix}; found {item} of type {type(item)}")

        return table

    def __init__(self, path: Union[str, os.PathLike[str]] = SETTINGS_FILE_NAME,
                 environment: bool = True, prefix: tuple[str, ...] = (),
                 fallbacks: _Chain = ()) -> None:
        if environment:
            path = os.getenv('RECHU_SETTINGS_FILE', path)

        try:
            with Path(path).open('r', encoding='utf-8') as settings_file:
                sections = tomlkit.load(settings_file)
        except FileNotFoundError:
            sections = tomlkit.document()

        self.sections = self._traverse(sections, prefix)

        self.environment = environment
        self.fallbacks = fallbacks
        self.prefix = prefix

    def get(self, section: str, key: str) -> str:
        """
        Retrieve a settings value from the file based on its `section` name,
        which refers to a TOML table grouping multiple settings, and its `key`,
        potentially with an environment variable override.
        """

        env_name = f"RECHU_{section.upper()}_{key.upper().replace('-', '_')}"
        if self.environment and env_name in os.environ:
            return os.environ[env_name]
        if section in self.sections:
            group = self.sections[section]
        else:
            group = None
        if not isinstance(group, dict) or key not in group:
            if self.fallbacks:
                return self._get_fallback(self.fallbacks).get(section, key)
            raise KeyError(f'{section} is not a section or does not have {key}')
        return str(group[key])

    @staticmethod
    def _get_section_comments(section: Union[Item, Container]) -> _SectionComments:
        comments: dict[str, list[str]] = {}
        comment: list[str] = []
        if isinstance(section, (Table, OutOfOrderTableProxy)):
            for key, value in section.value.body:
                if isinstance(value, Comment):
                    comment.append(str(value).lstrip('# '))
                else:
                    if key is not None:
                        comments[key.key] = comment
                    comment = []

        return comments

    def get_comments(self) -> _DocumentComments:
        """
        Retrieve comments of the settings by section.

        This retrieves comments for a setting from the settings file latest in
        the chain that has comments. Only comments preceding the setting are
        preserved.
        """

        comments: _DocumentComments = {}
        if self.fallbacks:
            comments = self._get_fallback(self.fallbacks).get_comments()
        for table in self.sections:
            section = self.sections[table]
            # Keep default comments over comments later in chain
            comments.setdefault(table, {})
            new_comments = self._get_section_comments(section).items()
            comments[table].update(
                (key, comment)
                for key, comment in new_comments
                if key not in comments[table]
            )

        return comments

    def _update_document(self, document: tomlkit.TOMLDocument,
                         table: str, comments: _DocumentComments) -> None:
        section = self.sections[table]
        if isinstance(section, (Table, OutOfOrderTableProxy)):
            table_comments = comments.get(table, {})
            target: Table = document.setdefault(table, tomlkit.table())
            for key in section:
                if key not in target:
                    for comment in table_comments.get(key, []):
                        target.add(tomlkit.comment(comment))
                target[key] = self.get(table, key)
        else:
            document.setdefault(table, section)

    def get_document(self) -> tomlkit.TOMLDocument:
        """
        Reconstruct a TOML document with overrides from environment variables,
        default values and comments from fallbacks.
        """

        if self.fallbacks:
            document = self._get_fallback(self.fallbacks).get_document()
        else:
            document = tomlkit.document()

        comments = self.get_comments()
        for table in self.sections:
            self._update_document(document, table, comments)

        return document

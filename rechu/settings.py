"""
Settings module.
"""

import os
from pathlib import Path
from typing import Union
import tomlkit
from tomlkit.items import Comment, Table
from typing_extensions import Required, TypedDict

class _SettingsFile(TypedDict, total=False):
    path: Required[Union[str, os.PathLike[str]]]
    environment: bool
    prefix: tuple[str, ...]

Chain = tuple[_SettingsFile, ...]

SETTINGS_FILE_NAME = 'settings.toml'

class Settings:
    """
    Settings reader and provider.
    """

    FILES: Chain = (
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
    def _get_fallback(cls, fallbacks: Chain) -> "Settings":
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

    def __init__(self, path: Union[str, os.PathLike[str]] = SETTINGS_FILE_NAME,
                 environment: bool = True, prefix: tuple[str, ...] = (),
                 fallbacks: Chain = ()) -> None:
        if environment:
            path = os.getenv('RECHU_SETTINGS_FILE', path)

        try:
            with Path(path).open('r', encoding='utf-8') as settings_file:
                sections = tomlkit.load(settings_file)
        except FileNotFoundError:
            sections = tomlkit.document()

        for group in prefix:
            sections = sections.get(group, {})
        self.sections: Union[Table, tomlkit.TOMLDocument] = sections

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
        group = self.sections.get(section)
        if not isinstance(group, dict) or key not in group:
            if self.fallbacks:
                return self._get_fallback(self.fallbacks).get(section, key)
            raise KeyError(f'{section} is not a section or does not have {key}')
        return str(group[key])

    def get_comments(self) -> dict[str, dict[str, list[str]]]:
        """
        Retrieve comments of the settings by section.

        This retrieves comments for a setting from the settings file latest in
        the chain that has comments. Only comments preceding the setting are
        preserved.
        """

        comment: list[str] = []
        comments: dict[str, dict[str, list[str]]] = {}
        if self.fallbacks:
            comments = self._get_fallback(self.fallbacks).get_comments()
        for table, section in self.sections.items():
            comments.setdefault(table, {})
            for key, value in section.value.body:
                if isinstance(value, Comment):
                    comment.append(str(value).lstrip('# '))
                else:
                    # Only keep default comments
                    if key is not None and key.key not in comments[table]:
                        comments[table][key.key] = comment
                    comment = []

        return comments

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
        for section, table in self.sections.items():
            table_comments = comments.get(section, {})
            target: Table = document.setdefault(section, tomlkit.table())
            for key in table:
                if key not in target:
                    for comment in table_comments.get(key, []):
                        target.add(tomlkit.comment(comment))
                target[key] = self.get(section, key)

        return document

"""
Settings module.
"""

import os
from pathlib import Path
import tomlkit
from tomlkit.items import Comment, Item
from typing_extensions import Required, TypedDict, Union

class _SettingsFile(TypedDict, total=False):
    path: Required[str]
    environment: bool
    prefix: tuple[str, ...]

Chain = tuple[_SettingsFile, ...]

class Settings:
    """
    Settings reader and provider.
    """

    FILES: Chain = (
        {
            'path': 'settings.toml'
        },
        {
            'path': 'pyproject.toml',
            'environment': False,
            'prefix': ('tool', 'rechu')
        },
        {
            'path': Path(__file__).parent / 'settings.toml',
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

    def __init__(self, path: Union[str, os.PathLike] = 'settings.toml',
                 environment: bool = True, prefix: tuple[str, ...] = (),
                 fallbacks: Chain = ()) -> None:
        if environment:
            path = os.getenv('RECHU_SETTINGS_FILE', path)

        try:
            with Path(path).open('r', encoding='utf-8') as settings_file:
                self.document = tomlkit.load(settings_file)
        except FileNotFoundError:
            self.document = tomlkit.TOMLDocument()

        sections = self.document
        for group in prefix:
            sections = sections.get(group, {})
        self.sections: dict[str, dict[str, str]] = sections

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

    def get_comments(self) -> dict[str, dict[str, list[Comment]]]:
        """
        Retrieve comments of the settings by section.
        """

        comment: list[Comment] = []
        comments: dict[str, dict[str, list[Comment]]] = {}
        if self.fallbacks:
            comments = self._get_fallback(self.fallbacks).get_comments()
        for table, section in self.document.items():
            comments.setdefault(table, {})
            for key, value in section.value.body:
                if isinstance(value, Comment):
                    comment.append(value)
                elif isinstance(value, Item):
                    comments[table].setdefault(key, [])
                    comments[table][key].extend(comment)
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
            document.setdefault(section, tomlkit.table())
            for key in table:
                if key not in document[section]:
                    for comment in table_comments.get(key, []):
                        document[section].add(comment)
                document[section][key] = self.get(section, key)

        return document

"""
Settings module.
"""

import os
from pathlib import Path
from typing import Optional
import tomlkit

class Settings:
    """
    Settings reader and provider.
    """

    _singleton: Optional["Settings"] = None
    _defaults: Optional["Settings"] = None

    @classmethod
    def get_settings(cls) -> "Settings":
        """
        Retrieve the settings singleton.
        """

        if cls._singleton is None:
            cls._singleton = Settings()

        return cls._singleton

    @classmethod
    def _get_defaults(cls) -> "Settings":
        if cls._defaults is None:
            cls._defaults = Settings('settings.toml.example', environment=False)

        return cls._defaults

    @classmethod
    def clear(cls) -> None:
        """
        Remove the singleton instance.
        """

        cls._singleton = None
        cls._defaults = None

    def __init__(self, settings_filename: str = 'settings.toml',
                 environment: bool = True) -> None:
        if environment:
            settings_filename = os.getenv('RECHU_SETTINGS_FILE',
                                          settings_filename)
        settings_path = Path(settings_filename)
        self.sections: dict[str, dict[str, str]] = {}
        try:
            with settings_path.open('r', encoding='utf-8') as settings_file:
                self.sections = tomlkit.load(settings_file)
        except FileNotFoundError:
            pass
        self.environment = environment

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
            if self is not self._get_defaults():
                return self._get_defaults().get(section, key)
            raise KeyError(f'{section} is not a section or does not have {key}')
        return str(group[key])

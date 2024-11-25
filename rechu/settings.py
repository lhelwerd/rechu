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

    @classmethod
    def get_settings(cls) -> "Settings":
        """
        Retrieve the settings singleton.
        """

        if cls._singleton is None:
            cls._singleton = Settings()

        return cls._singleton

    @classmethod
    def clear(cls) -> None:
        """
        Remove the singleton instance.
        """

        cls._singleton = None

    def __init__(self) -> None:
        settings_filename = os.getenv('RECHU_SETTINGS_FILE', 'settings.toml')
        settings_path = Path(settings_filename)
        with settings_path.open('r', encoding='utf-8') as settings_file:
            settings = tomlkit.load(settings_file)
        self.settings = settings

    def get(self, section: str, key: str) -> str:
        """
        Retrieve a settings item from the file, potentially with an environment
        variable override.
        """

        env_name = f"RECHU_{section.upper()}_{key.upper().replace('-', '_')}"
        if env_name in os.environ:
            return os.environ[env_name]
        group = self.settings[section]
        if not isinstance(group, dict) or key not in group:
            raise KeyError(f'{section} is not a section or does not have {key}')
        return str(group[key])

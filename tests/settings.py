"""
Tests for settings module.
"""

from collections.abc import Callable
import json
from pathlib import Path
from typing import Any, TypeVar, cast
import unittest
from unittest.mock import patch
from typing_extensions import override
from tomlkit.items import Table
from rechu.settings import Settings

CT = TypeVar("CT", bound=Callable[..., Any])

def patch_settings(settings: dict[str, str]) -> Callable[[CT], CT]:
    """
    Patch the environment variables with overrides for settings.
    """

    def decorator(test_method: CT) -> CT:
        return cast(CT, patch.dict("os.environ", settings)(test_method))

    return decorator

class SettingsTestCase(unittest.TestCase):
    """
    Test case base class which replaces the settings file with example settings.
    """

    @override
    def setUp(self) -> None:
        super().setUp()
        Settings.clear()
        patcher = patch.dict('os.environ',
                             {'RECHU_SETTINGS_FILE': 'tests/settings.toml'})
        cast(Callable[[], None], patcher.start)()
        self.addCleanup(cast(Callable[[], None], patcher.stop))

    @override
    def tearDown(self) -> None:
        super().tearDown()
        Settings.clear()

class SettingsTest(SettingsTestCase):
    """
    Tests for settings reader and provider.
    """

    def test_get_settings(self) -> None:
        """
        Test retrieving the settings singleton.
        """

        settings = Settings.get_settings()
        self.assertIs(settings, Settings.get_settings())

    def test_clear(self) -> None:
        """
        Test clearing the singleton instance.
        """

        settings = Settings.get_settings()
        Settings.clear()
        self.assertIsNot(settings, Settings.get_settings())

    def test_get(self) -> None:
        """
        Test retrieving a settings item.
        """

        settings = Settings.get_settings()
        self.assertEqual(settings.get('data', 'path'), '.')
        with patch.dict('os.environ', {'RECHU_DATA_PATH': '/tmp'}):
            self.assertEqual(settings.get('data', 'path'), '/tmp')

        with self.assertRaises(KeyError):
            _ = settings.get('missing', 'path')

        for section in ('data', 'other'):
            pattern = f'{section} is not a section or does not have ?'
            with self.assertRaisesRegex(KeyError, pattern):
                _ = settings.get(section, '?')

        # Defaults from fallback chain
        self.assertEqual(settings.get('database', 'foreign_keys'), 'ON')

        # Custom property
        self.assertEqual(settings.get('database', '_custom_prop'), 'ignore')

    def test_get_prefix(self) -> None:
        """
        Test retrieving a settings item from a settings file with prefixes.
        """

        prefix_settings = Settings(path='tests/settings.missing.toml',
                                   environment=False,
                                   fallbacks=(
                                       {
                                           'path': 'tests/settings.prefix.toml',
                                           'environment': False,
                                           'prefix': ('tool', 'rechu')
                                       },
                                       {
                                           'path': 'rechu/settings.toml',
                                           'environment': False
                                       }
                                   ))
        self.assertEqual(prefix_settings.get('data', 'path'), '.')
        self.assertEqual(prefix_settings.get('data', 'pattern'),
                         'samples/receipt*.yml')
        self.assertEqual(prefix_settings.get('database', 'foreign_keys'), 'ON')

        chain_settings = Settings(path='tests/settings.missing.toml',
                                  environment=False,
                                  fallbacks=(
                                      {
                                          'path': 'tests/settings.prefix.toml',
                                          'environment': False
                                      },
                                  ))
        # A fallback with different parameters remains unique
        with self.assertRaises(KeyError):
            _ = chain_settings.get('data', 'path')

    def test_get_missing(self) -> None:
        """
        Test retrieving a settings item with a missing settings file.
        """

        environ = {
            'RECHU_SETTINGS_FILE': 'samples/settings.toml.missing',
            'RECHU_DATA_PATH': '/tmp'
        }
        with patch.dict('os.environ', environ):
            settings = Settings.get_settings()
            self.assertEqual(settings.get('data', 'path'), '/tmp')
            self.assertEqual(settings.get('data', 'pattern'), '.')
            with self.assertRaises(KeyError):
                _ = settings.get('missing', 'path')

    def _get_comments(self, comment: str) -> list[str]:
        index = 0
        length = 79
        comments: list[str] = []
        while 0 <= index + length < len(comment):
            end = comment.rfind(" ", index, index + length)
            comments.append(comment[index:end].lstrip())
            index = end + 1
        if index < len(comment):
            comments.append(comment[index:].lstrip())

        return comments

    def test_get_comments(self) -> None:
        """
        Test retrieving comments of the settings by section.
        """

        settings = Settings.get_settings()
        actual = settings.get_comments()
        expected: dict[str, dict[str, list[str]]] = {}
        schema_path = Path('schema/settings.json')
        with schema_path.open('r', encoding='utf-8') as schema_file:
            schema = \
                cast(dict[str, dict[str, dict[str, dict[str, dict[str, str]]]]],
                     json.load(schema_file))
            for section, defs in schema["$defs"].items():
                if section != 'settings':
                    expected[section] = {}
                    for key, prop in defs["properties"].items():
                        expected[section][key] = \
                            self._get_comments(prop["description"])

                        # Test individual settings in subtests for better diff
                        with self.subTest(section=section, key=key):
                            self.assertEqual(actual.get(section, {}).get(key),
                                             expected[section][key])

        expected['database']['_custom_prop'] = \
            ['Some property that does not exist in the fallbacks.']
        expected['_other'] = {}
        self.assertEqual(actual, expected)

    def test_get_document(self) -> None:
        """
        Test reconstructing a TOML document with overrides, default values and
        comments from fallbacks.
        """

        settings = Settings.get_settings()
        with patch.dict('os.environ', {'RECHU_DATA_PATH': '/tmp'}):
            document = settings.get_document()
            data = document['data']
            if not isinstance(data, Table):
                self.fail("Expected section table for data")
            self.assertEqual(data['path'], '/tmp')

            with self.assertRaises(KeyError):
                self.assertIsNotNone(document['missing'])
            with self.assertRaises(KeyError):
                self.assertIsNotNone(data['?'])

            database = document['database']
            if not isinstance(database, Table):
                self.fail("Expected section table for database")

            # Defaults from fallback chain
            self.assertEqual(database['foreign_keys'], 'ON')

            # Custom property
            self.assertEqual(database['_custom_prop'], 'ignore')

    def test_get_document_defaults(self) -> None:
        """
        Test reconstructing a TOML document with comments and complete file
        layout from default settings.
        """

        defaults = Settings(**Settings.FILES[-1])
        defaults_path = Path('rechu/settings.toml')
        with defaults_path.open('r', encoding='utf-8') as defaults_file:
            self.assertEqual(defaults.get_document().as_string(),
                             defaults_file.read())

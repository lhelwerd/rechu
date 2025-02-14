"""
Tests for settings module.
"""

import unittest
from unittest.mock import patch
from rechu.settings import Settings

class SettingsTestCase(unittest.TestCase):
    """
    Test case base class which replaces the settings file with example settings.
    """

    def setUp(self) -> None:
        Settings.clear()
        patcher = patch.dict('os.environ',
                             {'RECHU_SETTINGS_FILE': 'settings.toml.test'})
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self) -> None:
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
            settings.get('missing', 'path')
        with self.assertRaisesRegex(KeyError,
                                    'data is not a section or does not have ?'):
            settings.get('data', '?')

        # Defaults
        self.assertEqual(settings.get('database', 'foreign_keys'), 'ON')

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
                settings.get('missing', 'path')

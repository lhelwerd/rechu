"""
Configuration file for the Sphinx documentation builder.

For the full list of built-in configuration values, see the documentation:
https://www.sphinx-doc.org/en/master/usage/configuration.html
"""

# pylint: disable=invalid-name

from pathlib import Path
import sys

sys.path.insert(0, str(Path('..', '..').resolve()))

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'Receipt cataloging hub'
project_copyright = '2024-2025, Leon Helwerda'
author = 'Leon Helwerda'
release = '0.0.0'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'myst_parser',
    'sphinx.ext.apidoc',
    'sphinx.ext.autodoc',
    'sphinx.ext.intersphinx',
    'sphinx.ext.todo',
    'sphinx.ext.viewcode',
    'sphinx-jsonschema'
]

templates_path = ['_templates']
exclude_patterns = []

source_suffix = {
    '.md': 'markdown',
    '.rst': 'restructuredtext'
}

myst_enable_extensions = ["colon_fence"]
myst_heading_anchors = 3

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'alabaster'
html_static_path = ['_static']
html_theme_options = {
    'body_max_width': '1146px',
    'page_width': '1366px'
}

# -- Extension configuration -------------------------------------------------

apidoc_modules = [
    {
        'path': '../../rechu',
        'destination': 'code',
        'exclude_patterns': ['**/alembic/*']
    }
]

intersphinx_mapping = {
    'python': ('https://docs.python.org/3.12', None),
    'packaging': ('https://packaging.python.org/en/latest', None),
    'sqlalchemy': ('https://docs.sqlalchemy.org/en/20', None),
    'alembic': ('https://alembic.sqlalchemy.org/en/latest', None)
}

jsonschema_options = {
    'lift_definitions': True,
    'auto_reference': True
}

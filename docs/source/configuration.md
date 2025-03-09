# Configuration

The `rechu` module comes with default configuration settings which are meant to 
bring the cataloging service in a workable state, but still need fine-tuning 
for specific purposes. This document introduces the usual process of 
configuring the module (including which settings to focus on primarily), 
describes further methods by which settings can be adjusted and finally 
provides a reference of the available options.

## Introduction



## Specifying overrides

The {py:mod}`settings` subsystem of the module has a concept of a fallback 
chain, where there is a primary source of settings and additional sources which 
are looked up if previous sources did not provide a value for the setting. The 
fallback chain is defined as the following priority list of environments and 
file names:

1. Environment variables starting with `RECHU_`, followed by the section and 
   setting name in uppercase, with an underscore between the section and name.
2. A file targeted by the `RECHU_SETTINGS_FILE` environment variable.
3. The `settings.toml` file in the current working directory.
4. A `pyproject.toml` file in the current working directory, which contains 
   tables labeled `[tool.rechu.{section}]`.
5. The default settings file distributed with the package.

## Reference


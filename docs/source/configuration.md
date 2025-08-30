# Configuration

The `rechu` module comes with default configuration settings which are meant to 
bring the cataloging service in a workable state, but still need fine-tuning 
for specific purposes. This document introduces the usual process of 
configuring the module (including which settings to focus on primarily), 
describes further methods by which settings can be adjusted and finally 
provides a reference of the available options.

## Introduction

It is recommended to copy the default configuration settings file to a location 
from which you will use the module. In the source repository, the default 
settings is found in the file `rechu/settings.toml`, but if you installed the 
module from a package, it might be difficult to find it in the virtual 
environment or local site packages (depending on how it was installed). 
Therefore, you can obtain the settings file (if you don't have one yet) using 
the [`rechu config` command](commands.md#output-configuration). We also show 
the contents of the default settings file here:

```{literalinclude} ../../rechu/settings.toml
```

In this file, the most relevant options to adjust are the `path` and `pattern` 
settings in the `data` section and the `uri` of the `database` section. If the 
YAML files that represent your receipts, products and shops are not in the 
directory from which you run the `rechu` command (which should also be where 
you keep your `settings.toml`) then you should adjust the first two options. If 
the files are all together, change `path` to point to this directory. You can 
give a full, absolute path or the relative path from your working directory. If 
the YAML files are spread across multiple, possibly nested, directories, then 
use `pattern` to point to the directories which contain them beneath the 
`path`. The `format` could be adjusted to write files to a particular directory 
or with a specific filename pattern when the [`rechu new` 
command](commands.md#new-receipts-and-products) is used to interactively create 
new receipts. Similarly, you may adjust matching pattern for product metadata 
inventories via the `products` setting and the shop inventory path with the 
`shops` setting.

More importantly is the database connection URI. The URI consists of a protocol 
(which contains the SQL dialect and the driver to connect with), optionally the 
username, password, host and port to connect to, a path segment and possible 
additional parameters in a query string. For SQLite, you can use a local file 
`example.db` as shown in the default settings; if you use a relative path, then 
keep the three slashes, otherwise the absolute path is after two slashes with 
three slashes in total in the end. For PostgreSQL, the database connection URI 
looks like `postgresql+psycopg2://user:password@host:port/dbname?key=value&...` 
with optional parts to be filled in or left out.

:::{seealso}
More details on how to configure the PostgreSQL database connection URI is 
found in the <inv:sqlalchemy:std:label#postgresql_psycopg2> section of the 
<inv:sqlalchemy:std:label#postgresql_toplevel> dialect in SQLAlchemy.
:::

## Specifying overrides

The {py:mod}`rechu.settings` submodule has a concept of a fallback chain, where 
there is a primary source of settings and additional sources which are looked 
up if previous sources did not provide a value for the setting. The fallback 
chain is defined as the following priority list of environments and file names:

1. Environment variables starting with `RECHU_`, followed by the section and 
   setting name in uppercase, with an underscore between the section and name.
2. A file targeted by the `RECHU_SETTINGS_FILE` environment variable.
3. The `settings.toml` file in the current working directory.
4. A `pyproject.toml` file in the current working directory, which contains 
   tables labeled `[tool.rechu.{section}]`. Settings names remain the same.
5. The default settings file distributed with the package.

## Reference

The packaged settings file not only provides the known settings and the default 
values, but also indicates what the setting is for and how it could be changed 
using comments. These comments are not meant to be exhaustive, but function as 
a guideline of how to change them.

:::{tip}
```{eval-rst}
For a full reference of the recognized sections, settings and value formats, 
refer to the :ref:`settings` JSON schema.
```
:::

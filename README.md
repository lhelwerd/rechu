# Receipt cataloging hub

[![Coverage](https://github.com/lhelwerd/rechu/actions/workflows/coverage.yml/badge.svg)](https://github.com/lhelwerd/rechu/actions/workflows/coverage.yml)
[![Coverage Status](https://coveralls.io/repos/github/lhelwerd/rechu/badge.svg?branch=main)](https://coveralls.io/github/lhelwerd/rechu?branch=main)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=lhelwerd_rechu&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=lhelwerd_rechu)

This repository contains a Python module that implements a database system for 
reading digitized receipts for detailed product purchases. Currently, the 
receipts and some product metadata have to be written first in YAML files.

The module is written for Python 3.9+ and supported database backends are 
SQLite and PostgreSQL. It is currently in alpha phase and is meant to be 
developed with more features for reporting, external data and so on. Detailed 
information on changes for each version is found in the 
[changelog](https://github.com/lhelwerd/rechu/blob/main/CHANGELOG.md) file. 
Most recent information on installation, configuration, usage and programming 
interfaces is found in the [documentation](https://lhelwerd.github.io/rechu/).

## Installation

To obtain the latest release version of the module and its dependencies from 
PyPI, use `pip install rechu` or `poetry add rechu`.

Source releases of versions are available from 
[GitHub](https://github.com/lhelwerd/rechu/releases).

When using the source release or if this repository is cloned, then 
installation of the module is possible with `pip install` followed by either 
the release zip/tarball or the current directory. `make install` installs from 
the current directory. We recommend using virtual environments to keep your 
dependencies separate from global installation.

To install a development version of the module as a dependency, you can use 
`rechu @ git+https://github.com/lhelwerd/rechu.git@main#egg=rechu` in 
a `pyproject.toml` project dependencies or similar file.

## Running

After installation, the `rechu` command should be available in your environment 
to run various subcommands, but it has not been configured and set up with any 
data sources and database connection.

In order to run the module, first place a `settings.toml` file in the directory 
from which you will use the module, which might be the current directory. 
Either use `rechu config > settings.toml` or (when using the source release or 
if this repository is cloned) copy the example `rechu/settings.toml` file with 
default values to another `settings.toml` file, then edit the new file to 
adjust values in it. If you plan to use this package as a dependency in your 
own module, then you can also override the values in a `pyproject.toml` file 
using `[tool.rechu...]` sections.

To create the database schema in the database path defined in the settings, use 
`rechu create`. Then, you can create receipts and products with `rechu new`; 
this command writes the new receipts and product metadata to YAML files in the 
defined path/filename format and imports them to the database, keeping both in 
sync. You can also bulk-import YAML files for receipts and product inventories 
from the defined path, receipt subdirectory pattern and product pattern with 
`rechu read`; you can later use the same command to synchronize changes in YAML 
files to the database.

When you install a new version of this package, there may be database schema 
changes which need to be applied to continue using the current model. After 
backing up your database, you should run `rechu alembic upgrade head` to 
migrate your database to the proper version. This command will use the database 
connection configured in your `settings.toml` file.

Some additional scripts that do not use the database are available in the 
`scripts` directory in the repository. These are mostly meant for experiments, 
simple reporting and validation.

## Development and testing

The module is tested with unit tests that are run on pytest. In the repository, 
first install dependencies with `make setup_test`, then run unit tests using 
`make test`. Additionally, obtain coverage information by using `make coverage` 
to perform the unit tests and receive output in the form of a textual report 
and XML report. Finally, an HTML report is obtainable with `coverage html`.

Typing and style checks are also possible by first installing dependencies 
using `make setup_analysis`. Then, use `make mypy` to run the type checker and 
receive HTML and XML reports. Style checks are done by using `make pylint` for 
an aggregate report output.

The unit test coverage, typing coverage, style checks and schema validation is 
combined in one [GitHub Actions](https://github.com/lhelwerd/rechu/actions) 
workflow which is run on commits to the main branch and pull request changes. 
Unit test coverage is then stored for comparative purposes via the interface at 
[Coveralls](https://coveralls.io/github/lhelwerd/rechu). The tests and coverage 
results are combined with analysis results (including typing coverage by Mypy, 
code style checks from Pylint and schema validation) as part of a quality gate 
on [SonarCloud](https://sonarcloud.io/project/overview?id=lhelwerd_rechu).

## License

The receipt cataloging hub module is licensed under the MIT License. See the 
[license](https://github.com/lhelwerd/rechu/blob/main/LICENSE) file for more 
information.

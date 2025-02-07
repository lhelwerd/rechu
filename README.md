# Receipt cataloging hub

[![Coverage](https://github.com/lhelwerd/rechu/actions/workflows/coverage.yml/badge.svg)](https://github.com/lhelwerd/rechu/actions/workflows/coverage.yml)
[![Coverage Status](https://coveralls.io/repos/github/lhelwerd/rechu/badge.svg?branch=main)](https://coveralls.io/github/lhelwerd/rechu?branch=main)

This repository contains a Python module that implements a database system for 
reading digitized receipts for detailed product purchases. Currently, the 
receipts and some product metadata have to be written first in YAML files.

The module is written for Python 3.9+. It is currently in alpha phase and is 
meant to be developed with more features for reporting, external data and so 
on. Detailed information on changes for each version is found in the 
[changelog](CHANGELOG.md) file.

## Installation

Source releases of versions are available from 
[GitHub](https://github.com/lhelwerd/rechu/tags).

When using the source release or if this repository is cloned, then 
installation of the module is possible with `pip install` followed by either 
the release zip/tarball or the current directory. `make install` installs from 
the current directory. We recommend using virtual environments to keep your 
dependencies separate from global installation.

To install a development version of the module as a dependency, use 
`git+https://github.com/lhelwerd/rechu.git@main#egg=rechu` in 
a `requirements.txt` or similar. Other means of specifying a release of the 
module in order to use it as a dependency exists, see [requirements file 
format](https://pip.pypa.io/en/stable/reference/requirements-file-format/) for 
inspiration.

## Running

In order to run the module, first place a `settings.toml` file in the directory 
from which you will use the module, which might be the current directory. You 
can copy the `settings.toml.example` file to `settings.toml` and edit it to 
adjust values in it.

After installation, the `rechu` command should be available in your environment 
to run various subcommands. To create the database schema in the database path 
defined in the settings, use `rechu create`. Then, you can create receipts with 
`rechu new`; the new receipts are written both to YAML files in the defined 
path/filename format and imported to the database. You can also bulk-import 
YAML files from the defined path and subdirectory pattern with `rechu read`; 
you can later use the same command to synchronize changes in YAML files to the 
database.

When you install a new version of this package, there may be database schema 
changes. You should run `rechu alembic upgrade head` to migrate your database 
to the proper version. This command will use the database connection configured 
in your `settings.toml` file.

Some additional scripts that do not use the database are available in the 
`scripts` directory in the repository. These are mostly meant for experiments, 
simple reporting and validation.

## Testing

In the repository, run unit tests using `make test`. Additionally, obtain 
coverage information by first installing dependencies with `make setup_test`. 
Then, use `make coverage` to perform the unit tests and receive output in the 
form of a textual report and XML report. Finally, you could use `coverage html` 
to receive an HTML report.

Typing and style checks are also possible by first installing dependencies 
using `make setup_analysis`. Then, use `make mypy` to run the type checker and 
receive HTML and XML reports. Style checks are done by using `make pylint` for 
an aggregate report output.

## License

The module is licensed under the MIT License. See the [license](LICENSE) file 
for more information.

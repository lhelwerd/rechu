# Installation

As a Python package, `rechu` is meant to be easy to install. Additional 
[configuration](configuration.md) to use specific databases or external sources 
may add some extra steps, but this document outlines the common installation 
options for initial setup.

You should already have [Python](https://www.python.org/) installed. We support 
versions 3.9 through 3.13. We also recommend installing a virtual environment 
to keep the module and its dependencies in an isolated location that remains 
separate from system/user/global packages. If you choose to skip creating 
a virtual environment, then you still need to ensure you have a package manager 
such as `uv`, `pip` or `poetry` installed.

:::{seealso}
More details on how to set up your Python to install packages can be found on 
<inv:packaging:std:doc#tutorials/installing-packages>.
:::

## From PyPI released version (recommended)

You can install the latest released version of the Python package from the 
[PyPI package repository](https://pypi.org/) by using one of the following 
methods:

- Install directly from PyPI using `uv add rechu`, `pip install rechu` or 
  `poetry add rechu`, for example.
- Navigate to the [rechu PyPI project](https://pypi.org/project/rechu/), select 
  the tab to [download files](https://pypi.org/project/rechu/#files), choose 
  one of the distribution files to download (we recommend using wheels), and 
  after download you can install the package as a dependency using one of the 
  package managers, such as `uv add rechu-<VERSION>-py3-none-any.whl` for the 
  wheel or `uv add rechu-<VERSION>.tar.gz` for the tarball.
- Instead of downloading, you can also copy the download link and provide it to 
  `pip install`, `poetry add` or `uv add`.
- You could also (manually) craft a `pyproject.toml` or other requirements file 
  with a dependency selector for `rechu` and let your package manager install 
  your dependencies when setting up your own software environment. This is not 
  recommended, especially if you just want to use `rechu` and not wrap around 
  the module.

## From GitHub releases

Released versions are also published on GitHub along with an extract of the 
changelog that indicates the notable changes in the version. This can be seen 
as an alternative download location for the built distribution of the package.

You can find the same files for the wheel and the source distribution of the 
package on the [GitHub releases](https://github.com/lhelwerd/rechu/releases) 
for each version, along with the source of the entire repository at the moment 
of the release (based on Git tags) in zip and tarball forms. The wheel file of
the [latest GitHub release](https://github.com/lhelwerd/rechu/releases/latest)
should be preferred when installing the package from this source. You may again 
download a file and install it with `uv add <file>` or copy the link and 
provide it to `pip install <url>`, `poetry add <url>` or `uv add <url>`. Note 
that this source does not support easy upgrading through version selectors, so 
some manual edits would be needed if this method is used.

## From repository

If you just want to make use of the command-line capabilities of `rechu` and do 
not necessary want to reuse it in other code, another alternative is to install 
it from the source code in the repository.

For this scenario, we assume you have [Git](https://git-scm.com/) installed for 
CLI usage as well as [GNU make](https://www.gnu.org/software/make/).

1. Clone the [GitHub repository](https://github.com/lhelwerd/rechu) using the 
   Git command line program: `git clone https://github.com/lhelwerd/rechu.git`.
2. Enter the cloned directory: `cd rechu`.
3. Optionally, change to a specific tag corresponding to a released version of 
   the module: `git checkout vX.Y.Z`. If you skip this, then you install 
   a development version, which is **not a recommended installation method**.
3. Run `make install`. This uses `uv` or `pip` depending on whether the former 
   package manager is already installed or not.

## As a development dependency

:::{warning}
This is not a recommended method of installing the module.
:::

To install a development version of the module as a dependency of your own 
code, add `rechu @ git+https://github.com/lhelwerd/rechu.git@main#egg=rechu` in 
your `pyproject.toml` project dependencies or similar file, then install it 
using your dependency manager, such as `pip install .`, `poetry install .` or 
`uv add .`.

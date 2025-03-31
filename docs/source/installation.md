# Installation

As a Python package, `rechu` is meant to be easy to install. Additional 
[configuration](configuration.md) to use specific databases or external sources 
may add some extra steps, but this document outlines the common installation 
options for initial setup.

You should already have [Python](https://www.python.org/) installed. We support 
versions 3.9 through 3.12. We also recommend installing a virtual environment 
to keep the module and its dependencies in an isolated location that remains 
separate from system/user/global packages. If you choose to skip creating 
a virtual environment, then you still need to ensure you have a package manager 
such as `pip` or `poetry` installed. 

:::{seealso}
More details on how to set up your Python to install packages can be found on 
<inv:packaging:std:doc#tutorials/installing-packages>.
:::

## From PyPI released version (recommended)

```{todo}

Fill this in once we release versions.
```

## From GitHub releases

```{todo}

Fill this in once we release versions.
```

## From repository

For this scenario, we assume you have [Git](https://git-scm.com/) installed for 
CLI usage as well as [GNU make](https://www.gnu.org/software/make/).

1. Clone the [GitHub repository](https://github.com/lhelwerd/rechu) using the 
   Git command line program: `git clone https://github.com/lhelwerd/rechu.git`.
2. Enter the cloned directory: `cd rechu`.
3. Optionally, change to a specific tag corresponding to a released version of 
   the module: `git checkout vX.Y.Z`. If you skip this, then you install 
   a development version, which is **not a recommended installation method**.
3. Run `make install`.

## As a development dependency

:::{warning}
This is not a recommended method of installing the module.
:::

To install a development version of the module as a dependency of your own code 
or module, add `git+https://github.com/lhelwerd/rechu.git@main#egg=rechu` in 
your `requirements.txt`, `pyproject.toml` or similar file, then install it 
using your dependency manager, such as `pip install -r requirements.txt` or 
`poetry install`.

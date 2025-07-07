# Commands

After [installing](installation.md) and [configuring](configuration.md) the 
module, you should be able to use the `rechu` command from a CLI. This command 
has a number of subcommands which form the interface to accessing and mutating 
the receipt catalog database. This document describes the available subcommands 
and walks through them to discuss how they help with further setting up, 
filling in and making use of the database. 

(config)=
## Output configuration

One of the first commands that comes in useful for setting up the environment 
for cataloging receipts is the `rechu config` command. This command outputs the 
currently active configuration that the module is using, including any override 
from environment variables, but with comments as included in the packaged file 
with default settings. When no settings file has been set up, this essentially 
provides a copy of the settings file, which can be written to a customized file 
for further adjustments.

The command also allows filtering on section, and further on key, in which case 
it will output a section table heading with the settings defined in the section 
(or just the setting identified by that key, with the section table heading). 
Again, only original comments are provided, unless the settings are custom and 
thus not defined in the default settings. To generate a settings file based on 
a specific file such as `settings.toml`, use `rechu config -f settings.toml`.

(create)=
## Create schema

When you start with an empty database, then it is likely that it does not have 
a database schema defined yet. In order to create the tables, relations and 
other definitions in the database defined in your settings, use `rechu create`.

This command not only sets up your database, but also marks it as up to date 
with the current model revision, so that later changes to the data model take 
the correct base revision to perform the relevant further migrations from. 
Database upgrades are described in the <project:#alembic> section.

(new)=
## New receipts and products

When your database is available and ready, you are able start filling it in 
with receipt information, including product items, discounts and additional 
metadata. If you have not created any YAML files containing this data yet, then 
one method of creating them and adding them to the database in one go is using 
`rechu new`.

This command will interactively query you on properties of a receipt that you 
create. This includes primary metadata of the receipt, such as the date and 
shop from which the receipt was obtained, but also product details and possible 
discounts. For products, additional metadata that matches products on the 
current and other receipts can also be input. After all portions have been 
filled in, a YAML file is generated for the receipt and product metadata is 
added to a separate YAML inventory file (or several files if the data products 
setting contains multiple format specifications). Additionally, the receipt is 
imported into the database, as well as any related entities and their 
relations, such as product items, discounts and metadata matching fields.

The process to fill in all the information may be somewhat tedious. At various 
points, you can choose to move to the next portion of a receipt (which is 
usually done by inputting an empty string or zero, as indicated by the query) 
or to return to a menu where you can choose which step to take next (which is 
indicated by a query when a question mark, `?`, is a valid input). The menu 
displays the steps and a brief description when `?` or `help` is entered.

If at any point you made an error with inputting products or discounts, then 
you can use the menu's `edit` step to open an editor to change the YAML 
representation. This even allows editing the date and shop, which will also 
affect the filename of the receipt, but note that the time part of the date is 
lost if this is part of the filename pattern. You may also inspect the YAML 
format of the receipt and product metadata in a read-only form by entering 
`view` in the menu.

Once the menu has been invoked, additional steps to do must be provided 
manually, such as `products` and `discounts` to add additional products and 
discounts in an interactive manner, respectively. Additional metadata for 
earlier products may be created with the `meta` step. This includes writing 
assortments of product ranges which have a shared generic product whose 
properties are inherited. If a product is created with similar matchers or 
identifiers as an existing metadata item, then an opportunity is given to merge 
them together or to add more matcher fields to distinguish the former.

To finish the file generation and import after using the menu, use the `write` 
step. If you run the command as `rechu new -c`, then this step will ask for 
confirmation before making persistent changes. A failed write (which also 
happens if there are no products listed on the receipt) will display the YAML 
format and return you to the menu. It's possible to exit the process by 
entering `quit` in the menu (with a confirmation if the `-c` argument is 
provided) or pressing `Ctrl+C` at any point. The receipt is discarded and you 
are able to start again from scratch. Product metadata is only accepted if it 
matches the current product or later on any product on the receipt without 
leading to duplicate matches. If you wrote a faulty receipt or product 
metadata, then you could either externally edit the corresponding YAML file and 
synchronize it by [reading files](#read), or you can use another command to 
[delete](#delete) the receipt YAML file and database entry.

:::{tip}
In the menu, all steps are also recognized if only a number of initial 
characters is provided; the first step with that prefix is then chosen.
:::

On platforms with support for <inv:python:std:doc#library/readline>, the 
process is made slightly easier by providing completion suggestions for certain 
entries, such as shop identifiers, product labels, prices that a product had 
before, discount labels and products previously involved in a discount. To view 
which options are hinted at for each entry, press `Tab` (possibly twice if more 
than one option is available).

(read)=
## Read files

If you already have YAML files, or changed them manually, and you want to 
import them into the database, then `rechu read` will read those files from the 
data path (specifically receipt files in subdirectories matching the data 
pattern and data format settings as well as product inventories matching the 
data products setting). Any existing entries corresponding with the filenames 
are updated with changes in the YAML file. Additionally, files that have 
entries that are missing in the database are created there, and product 
metadata no longer in the YAML inventories is deleted from the database. This 
is a bulk method of synchronizing the database with the YAML files. For 
deleting receipts, see the [delete](#delete) command.

(delete)=
## Delete entries

With `rechu delete` or the shorthand `rechu rm`, you can remove entries from 
the database as well as the corresponding YAML file from the filesystem. To do 
so, the subcommand requires additional arguments to actually delete anything. 
One or more filenames can be provided, which may either be specified as a path 
or just as a filename. The database entry is uniquely identified by the 
filename (because it is meant to contain a specific timestamp) and the path 
itself is reconstructed by using the data pattern to locate the file for 
deletion.

In case you only want to remove an entry from the database, you can indicate so 
with `rechu rm --keep FILENAME.yml`. This could be useful to remove a receipt 
from the live database for further editing before importing it again, or to 
rename it, for example.

(dump)=
## Dump entries

If you have a database filled with entries but are missing some or all of your 
YAML files, you can request the database to export everything to YAML files 
using `rechu dump`. This will create any YAML file for receipts and product 
inventories when the corresponding file is not found, so that existing files 
are kept as is. If you truly want to overwrite files, then first delete them. 
A safer approach would be to dump all the files to a new data path, for example 
with `RECHU_DATA_PATH=export rechu dump` to write everything to a new `export` 
directory. Any missing directories in the data pattern and product format 
settings structure are also created.

It is also possible to select specific entries to export, by providing one or 
more filenames to the command. This reduces the work needed to locate database 
entries for export in case a lot of them already exist, but you would need to 
know which particular files are missing.

(alembic)=
## Alembic migration

:::{important}
Before performing a database migration, we strongly recommend to back up your 
database, either by copying your `.db` file (SQLite) or using the procedures 
available to your database management system (such as in 
[PostgreSQL](https://www.postgresql.org/docs/current/backup.html)).
:::

When new versions of the package arrive, we might provide additions or changes 
to the data model to capture more details from receipts (and other entities), 
leading to more functionality that we can support. This means that existing 
databases require an upgrade as well to continue to reflect the model that the 
code makes use of and assumes to have. We use `alembic` to create migration 
steps which allow upgrading and downgrading. To upgrade to the latest revision 
available for your module's version, run `rechu alembic upgrade head`. This 
upgrades your database in online mode.

For more complicated setups or when the database structure cannot be adjusted 
by the same database user that connects to it normally, it may be relevant to 
perform upgrades through SQL scripts. It is possible to retrieve such scripts 
by adding an argument to the command as in `rechu alembic upgrade --sql head`.

:::{seealso}
More details on the offline migration scripts provided by `alembic` is found in 
<inv:alembic:std:doc#offline>. Note that direct use of `alembic` is shown in 
that document, while we recommend using `rechu alembic` before the further 
subcommands to set up the environment correctly.
:::

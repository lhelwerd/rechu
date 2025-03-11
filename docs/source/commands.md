# Commands

After [installing](installation.md) and [configuring](configuration.md) the 
module, you should be able to use the `rechu` command from a CLI. This command 
has a number of subcommands which form the interface to accessing and mutating 
the receipt catalog database. This document describes the available subcommands 
and walks through them to discuss how they help with further setting up, 
filling in and making use of the database. 

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
## New: Create receipts

When your database is available and ready, you can start filling it in with 
receipt information. If you have not created any YAML files for them yet, then 
one method of creating them and adding them to the database in one go is using 
`rechu new`.

This command will interactively query you on properties of a receipt that you 
create. This includes metadata of the receipt, such as the date and shop from 
which the receipt was obtained, but also product details and possible 
discounts. After all portions have been filled in, the YAML file is generated 
and the receipt is imported into the database, as well as any related entities 
(product items and discounts).

The process to fill in all the information may be somewhat tedious and it is 
relevant to see at which points you can choose to move to the next portion of 
a receipt (which is usually done by inputting an empty string or zero, as 
indicated by the query). Going back is currently not possible. If at any point 
you made an error, then you can choose to exit the process by pressing `Ctrl+C` 
and starting again from scratch. If you made a faulty receipt, then you could 
either edit the YAML file and synchronize it by [reading files](#read) or 
[delete](#delete) the receipt YAML file and database entry.

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
data path (including subdirectories matching the data pattern setting). Any 
existing entires corresponding with the filenames are updated with changes in 
the YAML file, while files that have missing entries are created in the 
database. This is a bulk method of synchronizing the database with the YAML 
files.

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
using `rechu dump`. This will create any YAML file for entries when the file is 
not found, so that existing file are kept as is. If you truly want to overwrite 
files, then first delete them. A safer approach would be to dump all the files 
to a new data path, for example with `RECHU_DATA_PATH=export rechu dump` to 
write everything to a new `export` directory. Any missing directories in the 
data pattern structure are also created.

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

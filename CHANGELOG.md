# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and we adhere to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- Avoid conflict with existing product metadata when splitting range products
- Create directories when writing receipt/metadata files in `new` subcommand.
- Correct spaces between options in meta prompt of `new` subcommand.
- Update suggestions for indicators and prices from products added to the 
  receipt for meta step of `new` subcommand.

## [0.0.2] - 2025-11-15

### Added

- Support for Python 3.14 added.
- Shop inventory metadata added.
- Shop metadata definition for discrete discount indicators allows for more 
  matches with discounted products.
- Mention how many product items have been matched with discounts and product 
  metadata during their respective steps in `new` subcommand.
- Mention total price and discount of receipt in `new` subcommand.
- String representations for global tride item numbers (GTIN) added.

### Changed

- Cancel adding product item in `new` subcommand during label, price or 
  discount indicator input, similar to discount items and product metadata. 
  When an existing product was matched, then a cancel allows creating fresh 
  metadata.
- Do not display metadata matching status of previous product item in `new` 
  subcommand if reaching the product step from the menu.
- Limit addition of discounts and product metadata in `new` subcommand unless 
  `--more` argument is used, while accepting more specific metadata when there 
  are multiple or partial matches.
- Suggestions for discounted products are filtered when they have been used in 
  `new` subcommand unless `--more` argument is used.
- Augment, deduplicate or split off existing product metadata fields during 
  `new` subcommand.
- Show the generic product when the metadata view substep is used in the `new` 
  subcommand.
- Display all prepared product metadata when the view step is used multiple 
  times in the `new` subcommand.
- Edit all prepared product metadata when the edit substep is used for the meta 
  step from the menu of the `new` subcommand, matching all with the products on 
  the receipt.
- Product metadata fields and substeps like view, edit, range and split are now 
  autocompleted when a prefix is unput during the `new` subcommand, with 
  preference for substeps when available in context and mentioned in prompt.

### Removed

- Support for Python 3.9 dropped.

### Fixed

- Load products with generic and range fields with higher join depth.
- Avoid losing matched metadata for product items due to updates to products 
  without changes.
- Do not suggest to merge existing product with itself in `new` subcommand.
- Improve missing or invalid inventory files and invalid inputs for quantities 
  more gracefully.

## [0.0.1] - 2025-08-02

### Added

- Settings configuration generation through a subcommand added.
- Product inventory and receipt database dump through a subcommand added.
- Support for PostgreSQL added.
- Receipt file and database entry deletion through a subcommand added.
- Database migration support using Alembic through a subcommand added.
- Initial version with database schema creation and YAML file reading and 
  writing (interactive step-based with fallback menu) for database import of 
  receipts and product metadata with assortment specifiers of product ranges.

### Changed

- Read and new commands keep product metadata in sync between YAML files and 
  database inventories, thus they delete stale database entities as well.
- Prices of products on receipts are compared against prices in product 
  metadata after dividing the former by the amount of the item, if possible; 
  for quantities with units, the product item must have the normalized unit.
- Add cascade deletes for receipt products/discounts.

### Fixed

- Correct precision of prices during serialization

[Unreleased]: https://github.com/lhelwerd/rechu/compare/v0.0.2...HEAD
[0.0.2]: https://github.com/lhelwerd/rechu/releases/tag/v0.0.2
[0.0.1]: https://github.com/lhelwerd/rechu/releases/tag/v0.0.1

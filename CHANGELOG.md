# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and we adhere to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Settings configuration generation through a subcommand added.
- Product inventory and receipt database dump through a subcommand added.
- Support for PostgreSQL added.
- Receipt file and database entry deletion through a subcommand added.
- Database migration support using Alembic through a subcommand added.
- Initial version with database schema creation and YAML file reading and 
  writing (interactive step-based with fallback menu) for database import of 
  receipts and product metadata.

### Changed

- Read and new commands keep product metadata in sync between YAML files and 
  database inventories, thus they delete stale database entities as well.
- Prices of products on receipts are compared against prices in product 
  metadata after dividing the former by the amount of the item, if possible; 
  for quantities with units, the product item must have the normalized unit.
- Add cascade deletes for receipt products/discounts.

### Fixed

- Correct precision of prices during serialization

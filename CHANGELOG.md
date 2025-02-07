# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and we adhere to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Database migration support using Alembic through a subcommand added.
- Initial version with database schema creation and YAML file reading/writing 
  for database import.

### Changed

- Add cascade deletes for receipt products/discounts.

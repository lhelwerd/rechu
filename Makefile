COVERAGE=coverage
MYPY=mypy
PYRIGHT=basedpyright
ifeq (,$(shell which uv))
	PIP=python -m pip
else
	PIP=uv pip
endif
PYLINT=pylint
RUFF=ruff check
RM=rm -rf
SCRIPTS=scripts
SOURCES=rechu
DOCS=docs
TESTS=tests
TEST_NAME?=pytest
TEST=-m pytest $(TESTS) --junit-xml=test-reports/TEST-$(TEST_NAME).xml
TWINE=python -m twine
GITHUB_REPO=https://github.com/lhelwerd/rechu

.PHONY: all
all: coverage mypy pylint

.PHONY: release
release: test mypy pylint clean build tag push upload form

.PHONY: setup
setup:
	$(PIP) install .

.PHONY: setup_release
setup_release:
	$(PIP) install . --group release

.PHONY: setup_analysis
setup_analysis:
	$(PIP) install . --group analysis

.PHONY: setup_test
setup_test:
	$(PIP) install . --group test

.PHONY: setup_doc
setup_doc:
	$(PIP) install . --group docs

.PHONY: setup_postgres
setup_postgres:
	$(PIP) install .[postgres]

.PHONY: install
install: setup

.PHONY: pylint
pylint:
	$(PYLINT) $(SOURCES) $(TESTS) $(SCRIPTS) \
		--output-format=parseable \
		-d duplicate-code

.PHONY: ruff
ruff:
	$(RUFF) $(SOURCES) $(TESTS) $(SCRIPTS) \
		--output-format=json --output-file=ruff-report.json -e
	$(RUFF) $(SOURCES) $(TESTS) $(SCRIPTS)

.PHONY: mypy
mypy:
	$(MYPY) $(SOURCES) $(TESTS) $(SCRIPTS) \
		--html-report mypy-report \
		--cobertura-xml-report mypy-report \
		--junit-xml mypy-report/TEST-junit.xml \
		--no-incremental --show-traceback

.PHONY: pyright
pyright:
	$(PYRIGHT) $(SOURCES) $(TESTS) $(SCRIPTS)

.PHONY: test
test:
	python $(TEST)

.PHONY: coverage
coverage:
	$(COVERAGE) run --source=$(SOURCES) $(TEST)
	$(COVERAGE) report -m
	$(COVERAGE) xml -i -o test-reports/cobertura-$(TEST_NAME).xml

.PHONY: build
build:
	python -m build

.PHONY: get_version
get_version: get_toml_version get_init_version get_sonar_version get_changelog_version get_docs_version
	if [ "${TOML_VERSION}" != "${INIT_VERSION}" ] || [ "${TOML_VERSION}" != "${SONAR_VERSION}" ] || [ "${TOML_VERSION}" != "${CHANGELOG_VERSION}" ] || [ "${TOML_VERSION}" != "${DOCS_VERSION}" ]; then \
		echo "Version mismatch"; \
		exit 1; \
	fi
	$(eval VERSION=$(TOML_VERSION))

.PHONY: get_init_version
get_init_version:
	$(eval INIT_VERSION=v$(shell grep __version__ $(SOURCES)/__init__.py | sed -E "s/__version__ = .([0-9.]+)./\\1/"))
	$(info Version in __init__.py: $(INIT_VERSION))

.PHONY: get_toml_version
get_toml_version:
	$(eval TOML_VERSION=v$(shell grep "^version" pyproject.toml | sed -E "s/version = .([0-9.]+)./\\1/"))
	$(info Version in pyproject.toml: $(TOML_VERSION))

.PHONY: get_sonar_version
get_sonar_version:
	$(eval SONAR_VERSION=v$(shell grep projectVersion sonar-project.properties | cut -d= -f2))
	$(info Version in sonar-project.properties: $(SONAR_VERSION))

.PHONY: get_changelog_version
get_changelog_version:
	$(eval RAW_CHANGELOG_VERSION=$(shell grep "^## \[[0-9]\+\.[0-9]\+\.[0-9]\+\]" CHANGELOG.md | head -n 1 | sed -E "s/## \[([0-9]+\.[0-9]+\.[0-9]+)\].*/\1/"))
	$(eval ESCAPED_VERSION=$(subst .,\.,$(RAW_CHANGELOG_VERSION)))
	$(eval CHANGELOG_VERSION=v$(RAW_CHANGELOG_VERSION))
	$(info Version in CHANGELOG.md: $(CHANGELOG_VERSION))

.PHONY: get_docs_version
get_docs_version:
	$(eval DOCS_VERSION=v$(shell grep "^release" $(DOCS)/source/conf.py | sed -E "s/release = .([0-9.]+)./\\1/"))
	$(info Version in $(DOCS)/source/conf.py: $(DOCS_VERSION))

.PHONY: tag
tag: get_version
	git tag $(VERSION)

.PHONY: push
push: get_version
	git push origin $(VERSION)

.PHONY: upload
upload:
	$(TWINE) upload dist/*

.PHONY: form
form: get_version
	$(info Now upload the two distribution files to the GitHub release form:)
	open "$(GITHUB_REPO)/releases/new?tag=$(VERSION)&title=$(VERSION)&body=$(shell sed -n -E '/^## \[$(ESCAPED_VERSION)\]/,/^(## )?\[([0-9]+\.[0-9]+\.[0-9]|Unreleased)\]/ p' CHANGELOG.md | sed -E 's/^## \[($(ESCAPED_VERSION))\]/**\1**/; $$d' | python -c 'import sys;import urllib.parse;print(urllib.parse.quote_plus(sys.stdin.read()))')"
	open dist/

.PHONY: doc
doc:
	make html -C $(DOCS)

.PHONY: clean
clean:
	# Unit tests and coverage
	$(RM) .coverage htmlcov/ test-reports/
	# Typing coverage and code style formatting
	$(RM) .mypy_cache mypy-report/ pylint-report.txt ruff-report.json
	# Schema validation
	$(RM) jsonschema_report_*.json
	# Pip and distribution
	$(RM) src/ build/ dist/ rechu.egg-info/

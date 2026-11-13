EXTRAS ?=
GROUPS ?=
COVERAGE := coverage
MYPY := mypy
PYRIGHT := basedpyright
PYLINT := pylint
RUFF := ruff check
TWINE := twine
RUN_TEST := python
ifeq (,$(shell which uv 2>/dev/null))
	INSTALL_DEPS := python -m pip install .
define install_deps
	$(INSTALL_DEPS)$(if $(1),[$(1)]) $(foreach group,$(2),--group $(group))
endef
else
	INSTALL_DEPS := uv sync
	RUN_ANALYSIS := uv run --group analysis --frozen
	COVERAGE := $(RUN_ANALYSIS) $(COVERAGE)
	MYPY := $(RUN_ANALYSIS) $(MYPY)
	PYRIGHT := $(RUN_ANALYSIS) $(PYRIGHT)
	PYLINT := $(RUN_ANALYSIS) $(PYLINT)
	RUFF := $(RUN_ANALYSIS) $(RUFF)
	TWINE := uv run --group release --frozen $(TWINE)
	RUN_TEST := uv run --group test --frozen $(RUN_TEST)
define install_deps
	$(INSTALL_DEPS) --frozen $(if $(1),--extra $(1)) $(foreach group,$(2),--group $(group))
endef
endif
RM=rm -rf
SCRIPTS=scripts
SOURCES=rechu
DOCS=docs
DOCS_SOURCES=$(DOCS)/source
TESTS=tests
TEST_NAME?=pytest
TEST=-m pytest $(TESTS) --junit-xml=test-reports/TEST-$(TEST_NAME).xml
TREE=$(SOURCES) $(TESTS) $(SCRIPTS) $(DOCS_SOURCES)
GITHUB_REPO=https://github.com/lhelwerd/rechu

.PHONY: all
all: coverage mypy pyright pylint ruff

.PHONY: release
release: ensure_lock test mypy pyright pylint ruff clean build tag push upload form

.PHONY: setup
setup:
	$(call install_deps,$(EXTRAS),$(GROUPS))

.PHONY: setup_all
setup_all:
	$(call install_deps,postgres,release analysis test docs)

.PHONY: setup_release
setup_release:
	$(call install_deps,$(EXTRAS),release)

.PHONY: setup_analysis
setup_analysis:
	$(call install_deps,$(EXTRAS),analysis)

.PHONY: setup_test
setup_test:
	$(call install_deps,$(EXTRAS),test)

.PHONY: setup_doc
setup_doc:
	$(call install_deps,$(EXTRAS),docs)

.PHONY: setup_postgres
setup_postgres:
	$(call install_deps,postgres,$(GROUPS))

.PHONY: install
install: setup

.PHONY: lock
lock:
	uv lock --upgrade

.PHONY: ensure_lock
ensure_lock:
	uv sync --all-groups --locked

.PHONY: pylint
pylint:
	$(PYLINT) $(TREE) \
		--output-format=parseable \
		-d duplicate-code

.PHONY: ruff
ruff:
	$(RUFF) $(TREE)

.PHONY: mypy
mypy:
	$(MYPY) $(TREE) \
		--html-report mypy-report \
		--cobertura-xml-report mypy-report \
		--junit-xml mypy-report/TEST-junit.xml \
		--no-incremental --show-traceback

.PHONY: pyright
pyright:
	$(PYRIGHT) $(TREE)

.PHONY: test
test:
	$(RUN_TEST) $(TEST)

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
	$(eval DOCS_VERSION=v$(shell grep "^release" $(DOCS_SOURCES)/conf.py | sed -E "s/release = .([0-9.]+)./\\1/"))
	$(info Version in $(DOCS_SOURCES)/conf.py: $(DOCS_VERSION))

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

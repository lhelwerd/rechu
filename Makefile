COVERAGE=coverage
MYPY=mypy
PIP=python -m pip
PYLINT=pylint
RM=rm -rf
SCRIPTS=scripts
SOURCES=rechu
TESTS=tests
TEST_NAME?=pytest
TEST=-m pytest $(TESTS) --junit-xml=test-reports/TEST-$(TEST_NAME).xml

.PHONY: all
all: coverage mypy pylint

.PHONY: release
release: test mypy pylint clean build tag push upload

.PHONY: setup
setup:
	$(PIP) install .

.PHONY: setup_release
setup_release:
	$(PIP) install .[release]

.PHONY: setup_analysis
setup_analysis:
	$(PIP) install .[analysis]

.PHONY: setup_test
setup_test:
	$(PIP) install .[test]

.PHONY: setup_doc
setup_doc:
	$(PIP) install .[docs]

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

.PHONY: mypy
mypy:
	$(MYPY) $(SOURCES) $(TESTS) $(SCRIPTS) \
		--html-report mypy-report \
		--cobertura-xml-report mypy-report \
		--junit-xml mypy-report/TEST-junit.xml \
		--no-incremental --show-traceback

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

.PHONY: doc
doc:
	make html -C docs

.PHONY: clean
clean:
	# Unit tests and coverage
	$(RM) .coverage htmlcov/ test-reports/
	# Typing coverage and Pylint
	$(RM) .mypy_cache mypy-report/ pylint-report.txt jsonschema_report_*.json
	# Pip and distribution
	$(RM) src/ build/ dist/ rechu.egg-info/

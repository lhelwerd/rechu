COVERAGE=coverage
MYPY=mypy
PIP=python -m pip
PYLINT=pylint
RM=rm -rf
SOURCES=rechu
TESTS=tests
TEST=-m unittest discover -b -p '*.py' -s $(TESTS) -t .

.PHONY: all
all: coverage mypy pylint

.PHONY: release
release: test mypy pylint clean build tag push upload

.PHONY: setup
setup:
	$(PIP) install -r requirements.txt

.PHONY: setup_release
setup_release:
	$(PIP) install -r requirements-release.txt

.PHONY: setup_analysis
setup_analysis:
	$(PIP) install -r requirements-analysis.txt

.PHONY: setup_test
setup_test:
	$(PIP) install -r requirements-test.txt

.PHONY: install
install:
	$(PIP) install .

.PHONY: pylint
pylint:
	$(PYLINT) $(SOURCES) $(TESTS) \
		--output-format=parseable \
		-d duplicate-code

.PHONY: mypy
mypy:
	$(MYPY) $(SOURCES) $(TESTS) \
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
	$(COVERAGE) xml -i -o test-reports/cobertura.xml

.PHONY: build
build:
	python -m build

.PHONY: clean
clean:
	# Unit tests and coverage
	$(RM) .coverage htmlcov/ test-reports/
	# Typing coverage and Pylint
	$(RM) .mypy_cache mypy-report/ pylint-report.txt
	# Pip and distribution
	$(RM) src/ build/ dist/ rechu.egg-info/

#!/bin/bash -e

# Script to validate JSON schemas and the YAML files against those schemas.

PYTHON=python
if ! command -v $PYTHON 2>&1 >/dev/null; then
	PYTHON=python3
	if ! command -v $PYTHON 2>&1 >/dev/null; then
		echo "This command can only be run in a Python 3 environment." >&2
		exit 1
	fi
fi

realpath() {
	if [ ! -e "$1" ]; then
		echo "Error: Path '$1' does not exist" >&2
		return 1
	fi
	$PYTHON -c "import os, sys;print(os.path.realpath(sys.argv[1]))" "$1"
}

usage() {
	echo "Usage: $0 [data directory root] [data pattern] [products pattern]" >&2
}

SCRIPT_DIR=$(dirname "${BASH_SOURCE[0]}")
ROOT_DIR=$(realpath "$SCRIPT_DIR/..")
DATA_DIR="$ROOT_DIR"
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
	usage
	exit 0
fi
if [ ! -z $1 ]; then
	DATA_DIR=$(realpath "$1")
fi
DATA_PATTERN="20*"
if [ ! -z $2 ]; then
	DATA_PATTERN="$2"
fi
PRODUCTS_PATTERN="products"
if [ ! -z $3 ]; then
	PRODUCTS_PATTERN="$3"
fi
if [ -d "$DATA_DIR/$PRODUCTS_PATTERN" ]; then
	PRODUCTS_PATTERN="$PRODUCTS_PATTERN/*.yml"
elif ! compgen -G "$DATA_DIR/$PRODUCTS_PATTERN" >/dev/null; then
	PRODUCTS_PATTERN="$PRODUCTS_PATTERN*.yml"
fi
if [ -d $(compgen -G "$DATA_DIR/$DATA_PATTERN" | head -n 1) ]; then
	DATA_PATTERN="$DATA_PATTERN/*.yml"
fi
if ! compgen -G "$DATA_DIR/$PRODUCTS_PATTERN" >/dev/null; then
	usage
	echo "$DATA_DIR/$PRODUCTS_PATTERN: Products matching pattern not found" >&2
	exit 1
fi
if ! compgen -G "$DATA_DIR/$DATA_PATTERN" >/dev/null; then
	usage
	echo "$DATA_DIR/$DATA_PATTERN: Data directory pattern not found" >&2
	exit 1
fi

check() {
	schema=$1
	shift
	files=$*
	if [ "$schema" = "meta" ]; then
		args="--check-metaschema"
	else
		args="--schemafile $ROOT_DIR/$schema"
	fi
	if [ -t 0 ]; then
		args="$args --color always"
		green=$'\033[1;32m'
		off=$'\e[m'
	else
		green=""
		off=""
	fi
	set +e
	if [ "$schema" = "schema/receipt.json" ]; then
		output=$(check-jsonschema $args $files 2>&1 | grep -v "\d.\d\d\? is not a multiple of 0.01" | sed -e "$ s/^Schema validation errors were encountered.$//")
		if [ "$output" = "" ]; then
			echo "${green}ok${off} -- validation done"
			code=0
		else
			echo "$output"
			code=1
		fi
	else
		check-jsonschema $args $files
		code=$?
	fi
	if [ $code -ne 0 ]; then
		check-jsonschema --output-format json $args $files 2>/dev/null | $PYTHON $ROOT_DIR/scripts/format_json_schema_report.py $schema
	else
		echo '{}' | $PYTHON $ROOT_DIR/scripts/format_json_schema_report.py $schema
	fi
	set -e
}

echo "Validating schemas in $ROOT_DIR/schema against metaschema"
check meta schema/*.json

if [ -f "$ROOT_DIR/settings.toml" ]; then
	echo "Validating settings.toml"
	check schema/settings.json $ROOT_DIR/settings.toml
fi
echo "Validating rechu/settings.toml and tests/settings.toml"
check schema/settings.json --default-filetype toml $ROOT_DIR/rechu/settings.toml $ROOT_DIR/tests/settings.toml

echo "Validating products in $DATA_DIR/$PRODUCTS_PATTERN"
check schema/products.json $DATA_DIR/$PRODUCTS_PATTERN

echo "Validating receipts in $DATA_DIR/$DATA_PATTERN"
# Ignore multipleOf errors for values that have less precision than 0.01
green=$'\033[1;32m'
off=$'\e[m'
check schema/receipt.json $DATA_DIR/$DATA_PATTERN

echo "Validating pyproject.toml and tests/settings.prefix.toml"
check schema/pyproject.json $ROOT_DIR/pyproject.toml $ROOT_DIR/tests/settings.prefix.toml

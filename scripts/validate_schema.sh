#!/bin/bash -e

# Script to validate JSON schemas and the YAML files against those schemas.

realpath() {
	if [ ! -e "$1" ]; then
		echo "Error: Path '$1' does not exist" >&2
		return 1
	fi
	python -c "import os, sys;print(os.path.realpath(sys.argv[1]))" "$1"
}

SCRIPT_DIR=$(dirname "${BASH_SOURCE[0]}")
ROOT_DIR=$(realpath "$SCRIPT_DIR/..")
DATA_DIR="$ROOT_DIR"
if [ ! -z $1 ]; then
	DATA_DIR=$(realpath "$1")
fi
if [ ! -f "$DATA_DIR/products.yml" ] ; then
	echo "Usage: $0 [data directory root]" >&2
	echo "$DATA_DIR: Data directory/directories/products not found" >&2
	exit 1
fi

echo "Validating schemas in $ROOT_DIR/schema against metaschema"
check-jsonschema --check-metaschema $ROOT_DIR/schema/*.json

echo "Validating $DATA_DIR/products.yml"
check-jsonschema --schemafile $ROOT_DIR/schema/products.json $DATA_DIR/products.yml

echo "Validating receipts in $DATA_DIR/20*"
# Ignore multipleOf errors for values that have less precision than 0.01
green=$'\033[1;32m'
off=$'\e[m'
check-jsonschema --color always --schemafile $ROOT_DIR/schema/receipt.json $DATA_DIR/20*/*.yml | grep -v "\d.\d\d\? is not a multiple of 0.01" | sed -e "$ s/^Schema validation errors were encountered.$/${green}ok${off} -- validation done/"

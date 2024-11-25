#!/bin/bash -e

# Script to report on some product information without database.

realpath() {
	if [ ! -e "$1" ]; then
		echo "Error: Path '$1' does not exist" >&2
		return 1
	fi
	python -c "import os, sys;print(os.path.realpath(sys.argv[1]))" "$1"
}

SCRIPT_DIR=$(dirname "${BASH_SOURCE[0]}")
DATA_DIR=$(realpath "$SCRIPT_DIR/..")
if [ ! -z $1 ]; then
	DATA_DIR=$(realpath "$1")
fi
if ! ls $DATA_DIR/20* 1>/dev/null 2>&1; then
	echo "Usage: $0 [data directory root]" >&2
	echo "$DATA_DIR/20*: Data directory/directories not found" >&2
	exit 1
fi

grep "\- \[\d" $DATA_DIR/20*/*.yml | cut -d',' -f2 | sed -e "s/^ //" | sort | uniq -c | sort -n

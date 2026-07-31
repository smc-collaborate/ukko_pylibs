#!/usr/bin/env bash
PROJ_DIR="$(dirname "$(realpath -m "${BASH_SOURCE[0]}")")/../"

cd "${PROJ_DIR}" || exit 13

##################
#
rm -rf '.venv'

find . -name __pycache__ -exec rm -rf {} \;

find . -name '*.pyc' -exec rm -rf {} \;

echo "Erased .venv , __pycache__ & *.pyc files"

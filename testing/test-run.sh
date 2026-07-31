#!/bin/bash -eu

THIS_DIR="$(dirname "${BASH_SOURCE[0]}")"
cd "$THIS_DIR"

prettyData/test-PrettyTables.py file:samples/table-wide.json  --render=file:samples/render-barred.json

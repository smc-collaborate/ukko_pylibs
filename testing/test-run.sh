#!/bin/bash -eu

THIS_DIR="$(dirname "${BASH_SOURCE[0]}")"
cd "$THIS_DIR"

prettyData/test-run.sh

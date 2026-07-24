#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOYMENT_ROOT="${ROOT_DIR}/deployment"
DEPLOYMENT_DIR="${DEPLOYMENT_ROOT}/EnigmaFreeSurferSorting"
ZIP_PATH="${DEPLOYMENT_ROOT}/EnigmaFreeSurferSorting.zip"

rm -rf "$DEPLOYMENT_DIR"
mkdir -p "$DEPLOYMENT_DIR"

cp "$ROOT_DIR/README.md" "$DEPLOYMENT_DIR/"
cp "$ROOT_DIR/main.py" "$DEPLOYMENT_DIR/"
cp "$ROOT_DIR/validate_output.py" "$DEPLOYMENT_DIR/"
cp -R "$ROOT_DIR/sorter" "$DEPLOYMENT_DIR/"
cp -R "$ROOT_DIR/tests" "$DEPLOYMENT_DIR/"
mkdir -p "$DEPLOYMENT_DIR/jobs"
cp "$ROOT_DIR/jobs/submit_sort.sh" "$DEPLOYMENT_DIR/jobs/"

find "$DEPLOYMENT_DIR" -type d -name "__pycache__" -prune -exec rm -rf {} +
find "$DEPLOYMENT_DIR" -type f -name "*.pyc" -delete

(
    cd "$DEPLOYMENT_DIR"
    python3 -m unittest discover -s tests
    python3 -m py_compile main.py validate_output.py sorter/*.py
)

find "$DEPLOYMENT_DIR" -type d -name "__pycache__" -prune -exec rm -rf {} +
find "$DEPLOYMENT_DIR" -type f -name "*.pyc" -delete

find "$DEPLOYMENT_DIR" -exec touch -t 198001010000 {} +

rm -f "$ZIP_PATH"
(
    cd "$DEPLOYMENT_ROOT"
    find "$(basename "$DEPLOYMENT_DIR")" -print \
        | LC_ALL=C sort \
        | zip -X -q "$(basename "$ZIP_PATH")" -@
)

echo "Deployment package created: $ZIP_PATH"


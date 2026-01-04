#!/bin/bash
# scripts/init-shared-data-dir.sh
# Creates ~/.ktrdr/shared/ directory structure for sandbox instances
#
# This is a minimal version for M1. The full `ktrdr sandbox init-shared`
# command with --from and --minimal options comes in M5.

set -e

SHARED_DIR="${HOME}/.ktrdr/shared"

echo "Creating shared data directory: ${SHARED_DIR}"

mkdir -p "${SHARED_DIR}/data"
mkdir -p "${SHARED_DIR}/models"
mkdir -p "${SHARED_DIR}/strategies"

echo "Created:"
echo "  ${SHARED_DIR}/data/"
echo "  ${SHARED_DIR}/models/"
echo "  ${SHARED_DIR}/strategies/"
echo ""
echo "To populate with existing data:"
echo "  cp -r ./data/* ${SHARED_DIR}/data/"
echo "  cp -r ./models/* ${SHARED_DIR}/models/"
echo "  cp -r ./strategies/* ${SHARED_DIR}/strategies/"

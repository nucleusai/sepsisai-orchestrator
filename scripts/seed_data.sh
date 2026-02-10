#!/usr/bin/env bash
# =============================================================================
# seed_data.sh — Load sample PSV data into MongoDB via the CDA service.
# =============================================================================
#
# Usage:
#   ./scripts/seed_data.sh          (uses docker compose)
#   make seed                       (shortcut)
#
set -euo pipefail

echo "============================================"
echo " SepsisAI-Orchestrator — Data Seed"
echo "============================================"

# Verify sample data exists
DATA_DIR="data/sample"
PSV_COUNT=$(find "$DATA_DIR" -name "*.psv" 2>/dev/null | wc -l)

if [ "$PSV_COUNT" -eq 0 ]; then
    echo ""
    echo "ERROR: No .psv files found in $DATA_DIR/"
    echo ""
    echo "Please copy PSV files from the PhysioNet 2019 Challenge dataset:"
    echo "  https://physionet.org/content/challenge-2019/1.0.0/"
    echo ""
    echo "Example:"
    echo "  cp /path/to/training_setA/p00000*.psv data/sample/"
    echo ""
    exit 1
fi

echo ""
echo "Found $PSV_COUNT PSV file(s) in $DATA_DIR/"
echo "Starting CDA preprocessing pipeline..."
echo ""

docker compose run --rm cda-preprocessing

echo ""
echo "============================================"
echo " Seed complete!"
echo ""
echo " Start the platform:   docker compose up -d"
echo " Dashboard:            http://localhost:8501"
echo " AI API docs:          http://localhost:8000/docs"
echo "============================================"

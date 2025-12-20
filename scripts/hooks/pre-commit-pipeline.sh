#!/usr/bin/env bash
# Pre-commit hook: Regenerate enriched specs and validate on every commit
#
# This hook runs the same steps as GitHub Actions workflow:
#   1. Enrichment pipeline (python -m scripts.pipeline)
#   2. Spectral linting (python scripts/lint.py)
#
# DRY Principle: All methods use the same commands:
#   - Manual: make pipeline && make lint
#   - Pre-commit: this script (runs on every commit)
#   - GitHub Actions: same python commands
#
# This ensures idempotent, deterministic output between local and CI/CD.

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Detect Python interpreter
if [ -d ".venv" ]; then
    PYTHON=".venv/bin/python"
elif command -v python3 &> /dev/null; then
    PYTHON="python3"
else
    PYTHON="python"
fi

# =============================================================================
# STEP 1: Run Enrichment Pipeline
# =============================================================================
echo -e "${YELLOW}[1/2] Running F5 XC API enrichment pipeline...${NC}"
echo -e "${YELLOW}Executing: $PYTHON -m scripts.pipeline${NC}"

if ! $PYTHON -m scripts.pipeline; then
    echo -e "${RED}Pipeline failed! Please fix errors before committing.${NC}"
    exit 1
fi

# Stage any changes to enriched specs (output is directly in docs/)
# Note: openapi.json is in .gitignore (too large for GitHub), so we only stage domain specs
ENRICHED_CHANGES=$(git diff --name-only -- 'docs/specifications/api/*.json' 2>/dev/null | wc -l | tr -d ' ')

if [ "$ENRICHED_CHANGES" -gt 0 ]; then
    echo -e "${YELLOW}Staging $ENRICHED_CHANGES updated enriched spec files...${NC}"
    # Use --ignore-errors to skip ignored files like openapi.json
    git add --ignore-errors docs/specifications/api/*.json 2>/dev/null || true
    echo -e "${GREEN}Enriched specs updated and staged.${NC}"
else
    echo -e "${GREEN}No enriched spec changes detected.${NC}"
fi

# =============================================================================
# STEP 2: Run Spectral Linting (same as GitHub Actions)
# =============================================================================
echo -e "${YELLOW}[2/2] Running Spectral linting...${NC}"

# Check if Spectral is installed
if ! command -v spectral &> /dev/null; then
    echo -e "${YELLOW}Spectral not installed. Install with: npm install -g @stoplight/spectral-cli${NC}"
    echo -e "${YELLOW}Skipping Spectral linting (will run in CI/CD)${NC}"
else
    echo -e "${YELLOW}Executing: $PYTHON scripts/lint.py --input-dir docs/specifications/api${NC}"

    # Run linting - capture output but don't fail on lint issues
    # (matches GitHub Actions behavior with continue-on-error: true)
    if $PYTHON scripts/lint.py --input-dir docs/specifications/api; then
        echo -e "${GREEN}Spectral linting passed.${NC}"
    else
        echo -e "${YELLOW}Spectral linting completed with issues (non-blocking).${NC}"
    fi
fi

echo -e "${GREEN}Pre-commit pipeline complete.${NC}"
exit 0

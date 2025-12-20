#!/usr/bin/env bash
# Pre-commit hook: Regenerate enriched specs and validate on every commit
#
# IMPORTANT: This hook validates ALL files on every commit, including:
#   - All 270 original specs in specs/original/
#   - All 25 generated specs in docs/specifications/api/ (gitignored)
#   - Linting runs on ALL generated specs, not just staged files
#
# This hook runs the same steps as GitHub Actions workflow:
#   1. Enrichment pipeline (python -m scripts.pipeline)
#   2. Spectral linting (python scripts/lint.py --input-dir docs/specifications/api)
#
# DRY Principle: All methods use the same commands:
#   - Manual: make pipeline && make lint
#   - Pre-commit: this script (runs on every commit)
#   - GitHub Actions: same python commands
#
# This ensures idempotent, deterministic output between local and CI/CD.
# Linting is NEVER skipped - Spectral must be installed.

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
# STEP 2: Run Spectral Linting on ALL generated specs (same as GitHub Actions)
# =============================================================================
echo -e "${YELLOW}[2/2] Running Spectral linting on ALL generated specs...${NC}"

# Check if Spectral is installed - REQUIRED, never skip
if ! command -v spectral &> /dev/null; then
    echo -e "${RED}ERROR: Spectral CLI is not installed!${NC}"
    echo -e "${RED}Linting is REQUIRED and cannot be skipped.${NC}"
    echo -e "${YELLOW}Install with: npm install -g @stoplight/spectral-cli${NC}"
    exit 1
fi

echo -e "${YELLOW}Executing: $PYTHON scripts/lint.py --input-dir docs/specifications/api --fail-on-error${NC}"
echo -e "${YELLOW}Note: Validating ALL 25 generated specs (including gitignored files)${NC}"

# Run linting on ALL files in the directory - fail on errors to ensure clean specs
if $PYTHON scripts/lint.py --input-dir docs/specifications/api --fail-on-error; then
    echo -e "${GREEN}Spectral linting passed (all files validated).${NC}"
else
    LINT_EXIT_CODE=$?
    echo -e "${RED}Spectral linting failed with errors!${NC}"
    echo -e "${RED}Fix linting errors before committing.${NC}"
    exit $LINT_EXIT_CODE
fi

echo -e "${GREEN}Pre-commit pipeline complete.${NC}"
exit 0

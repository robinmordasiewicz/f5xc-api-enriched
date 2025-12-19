#!/usr/bin/env bash
# Pre-commit hook: Regenerate enriched specs and stage changes
#
# This hook ensures specs/enriched/ is always in sync with specs/original/
# by running the same pipeline used by make build and GitHub Actions.
#
# DRY Principle: All methods use the same command:
#   - Manual: make pipeline
#   - Pre-commit: this script
#   - GitHub Actions: python -m scripts.pipeline
#
# All call: python -m scripts.pipeline

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Running F5 XC API enrichment pipeline...${NC}"

# Check if original specs have changed (staged for commit)
ORIGINAL_CHANGED=$(git diff --cached --name-only -- 'specs/original/*.json' 2>/dev/null | wc -l | tr -d ' ')

# Check if scripts have changed (could affect output)
SCRIPTS_CHANGED=$(git diff --cached --name-only -- 'scripts/*.py' 'scripts/utils/*.py' 'config/*.yaml' 2>/dev/null | wc -l | tr -d ' ')

if [ "$ORIGINAL_CHANGED" -eq 0 ] && [ "$SCRIPTS_CHANGED" -eq 0 ]; then
    echo -e "${GREEN}No spec or script changes detected. Skipping pipeline.${NC}"
    exit 0
fi

echo "Detected changes: $ORIGINAL_CHANGED spec files, $SCRIPTS_CHANGED script/config files"

# Run the unified pipeline (same as make pipeline and GitHub Actions)
# This is the single source of truth for processing
if [ -d ".venv" ]; then
    PYTHON=".venv/bin/python"
elif command -v python3 &> /dev/null; then
    PYTHON="python3"
else
    PYTHON="python"
fi

echo -e "${YELLOW}Executing: $PYTHON -m scripts.pipeline${NC}"

if ! $PYTHON -m scripts.pipeline; then
    echo -e "${RED}Pipeline failed! Please fix errors before committing.${NC}"
    exit 1
fi

# Stage any changes to enriched specs
ENRICHED_CHANGES=$(git diff --name-only -- 'specs/enriched/*.json' 2>/dev/null | wc -l | tr -d ' ')

if [ "$ENRICHED_CHANGES" -gt 0 ]; then
    echo -e "${YELLOW}Staging $ENRICHED_CHANGES updated enriched spec files...${NC}"
    git add specs/enriched/*.json
    echo -e "${GREEN}Enriched specs updated and staged.${NC}"
else
    echo -e "${GREEN}No enriched spec changes detected.${NC}"
fi

# Also stage docs copy if present
if [ -d "docs/specs/enriched" ]; then
    # Copy enriched specs to docs
    cp -r specs/enriched/* docs/specs/enriched/ 2>/dev/null || true
    DOCS_CHANGES=$(git diff --name-only -- 'docs/specs/enriched/*.json' 2>/dev/null | wc -l | tr -d ' ')
    if [ "$DOCS_CHANGES" -gt 0 ]; then
        git add docs/specs/enriched/*.json
        echo -e "${GREEN}Docs specs also staged.${NC}"
    fi
fi

echo -e "${GREEN}Pre-commit pipeline complete.${NC}"
exit 0

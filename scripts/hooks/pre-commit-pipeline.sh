#!/usr/bin/env bash
# Pre-commit hook: Regenerate enriched specs on every commit
#
# This hook runs the enrichment pipeline unconditionally on every commit,
# ensuring docs/specifications/api/ is always in sync with specs/original/.
#
# DRY Principle: All methods use the same command:
#   - Manual: make pipeline
#   - Pre-commit: this script (runs on every commit)
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

# Run the unified pipeline on every commit (same as make pipeline and GitHub Actions)
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

echo -e "${GREEN}Pre-commit pipeline complete.${NC}"
exit 0

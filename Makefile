# F5 XC API Enrichment Pipeline Makefile
# Local builds produce identical output to GitHub Actions workflow
#
# Simplified two-folder architecture:
#   specs/original/   - READ-ONLY source from F5
#   specs/enriched/   - Merged domain specs only (no individual files)
#
# Usage:
#   make build      - Full pipeline (download → enrich → normalize → merge)
#   make clean      - Remove generated files
#   make install    - Install dependencies
#   make download   - Download specs only
#   make pipeline   - Run unified pipeline (enrich + normalize + merge)
#   make serve      - Serve docs locally
#
# The pipeline ensures deterministic output:
#   specs/original/   → READ-ONLY source from F5
#   specs/enriched/   → Merged domain specs
#       ├── api_security.json
#       ├── applications.json
#       ├── bigip.json
#       ├── billing.json
#       ├── cdn.json
#       ├── config.json
#       ├── identity.json
#       ├── infrastructure.json
#       ├── infrastructure_protection.json
#       ├── load_balancer.json
#       ├── networking.json
#       ├── nginx.json
#       ├── observability.json
#       ├── other.json
#       ├── security.json
#       ├── service_mesh.json
#       ├── shape_security.json
#       ├── subscriptions.json
#       ├── tenant_management.json
#       ├── vpn.json
#       ├── openapi.json    (master combined spec)
#       └── index.json      (spec metadata)

.PHONY: all build clean install download pipeline enrich normalize merge lint validate serve help check-deps venv pre-commit-install pre-commit-run pre-commit-uninstall

# Virtual environment
VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

# Default target
all: build

# Full pipeline - matches GitHub Actions workflow exactly
build: check-deps download pipeline copy-docs
	@echo ""
	@echo "Build complete. Output in:"
	@echo "  specs/enriched/           - Merged domain API specifications"
	@echo "  docs/specs/enriched       - Copy for GitHub Pages"
	@echo ""
	@echo "Run 'make serve' to preview locally"

# Create virtual environment
venv: $(VENV)/bin/activate

$(VENV)/bin/activate:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip

# Check dependencies are installed
check-deps:
	@test -d $(VENV) || { echo "Virtual environment missing. Run: make install"; exit 1; }
	@$(PYTHON) -c "import rich" 2>/dev/null || { echo "Python dependencies missing. Run: make install"; exit 1; }

# Install all dependencies
install: venv
	$(PIP) install -r requirements.txt
	@echo "Dependencies installed successfully"

# Download specifications from F5 (with ETag caching)
download:
	$(PYTHON) -m scripts.download --force

# Run unified pipeline (enrich → normalize → merge)
pipeline:
	$(PYTHON) -m scripts.pipeline

# Individual steps (for debugging or development)
enrich:
	$(PYTHON) -m scripts.enrich

normalize:
	$(PYTHON) -m scripts.normalize

merge:
	$(PYTHON) -m scripts.merge_specs

# Lint specifications with Spectral (requires: npm install -g @stoplight/spectral-cli)
lint:
	$(PYTHON) scripts/lint.py --input-dir specs/enriched

# Copy enriched specs to docs folder for GitHub Pages
copy-docs:
	@mkdir -p docs/specs
	@rm -rf docs/specs/enriched
	cp -r specs/enriched docs/specs/

# Validate specifications with live API (optional, requires credentials)
validate:
	@if [ -z "$$F5XC_API_TOKEN" ]; then \
		echo "F5XC_API_TOKEN not set. Skipping live validation."; \
	else \
		$(PYTHON) -m scripts.validate --dry-run; \
	fi

# Serve documentation locally
serve:
	@echo "Starting local server at http://localhost:8000"
	@echo "Scalar UI: http://localhost:8000/scalar/"
	@echo "Swagger UI: http://localhost:8000/swagger-ui/"
	@echo "Press Ctrl+C to stop"
	@cd docs && $(PYTHON) -m http.server 8000

# Clean generated files (preserves original specs)
clean:
	rm -rf specs/enriched
	rm -rf reports
	rm -rf docs/specs/enriched
	@echo "Cleaned generated files. Original specs preserved."

# Deep clean - removes everything including downloaded specs
clean-all: clean
	rm -rf specs/original
	rm -f .etag
	rm -f .version
	@echo "Deep clean complete. Run 'make download' to fetch specs."

# Quick rebuild - skip download, run pipeline only
rebuild: pipeline copy-docs

# Install pre-commit hooks
pre-commit-install: check-deps
	$(PYTHON) -m pre_commit install
	chmod +x scripts/hooks/pre-commit-pipeline.sh
	@echo "Pre-commit hooks installed successfully"

# Run pre-commit on all files (for CI or manual check)
pre-commit-run: check-deps
	$(PYTHON) -m pre_commit run --all-files

# Uninstall pre-commit hooks
pre-commit-uninstall:
	$(PYTHON) -m pre_commit uninstall
	@echo "Pre-commit hooks uninstalled"

# Help
help:
	@echo "F5 XC API Enrichment Pipeline"
	@echo ""
	@echo "Simplified two-folder architecture:"
	@echo "  specs/original/   - READ-ONLY source from F5"
	@echo "  specs/enriched/   - Merged domain specs only"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Main targets:"
	@echo "  build       Full pipeline (download → pipeline → copy-docs)"
	@echo "  rebuild     Quick rebuild (skip download, use existing original specs)"
	@echo "  serve       Start local server to preview docs"
	@echo "  clean       Remove generated files (keeps original specs)"
	@echo "  clean-all   Remove all generated files including downloads"
	@echo ""
	@echo "Pipeline:"
	@echo "  download    Download specs from F5"
	@echo "  pipeline    Run unified pipeline (enrich → normalize → merge)"
	@echo ""
	@echo "Individual steps (for debugging):"
	@echo "  enrich      Apply branding, acronyms, grammar"
	@echo "  normalize   Fix orphan refs, clean operations"
	@echo "  merge       Combine specs by domain"
	@echo "  lint        Validate specs with Spectral OpenAPI linter"
	@echo "  validate    Test with live API (needs credentials)"
	@echo ""
	@echo "Setup:"
	@echo "  install     Install Python and Node.js dependencies"
	@echo "  check-deps  Verify all dependencies are installed"
	@echo ""
	@echo "Pre-commit:"
	@echo "  pre-commit-install    Install git pre-commit hooks"
	@echo "  pre-commit-run        Run all pre-commit hooks manually"
	@echo "  pre-commit-uninstall  Remove pre-commit hooks"

# F5 XC API Enrichment Pipeline Makefile
# Local builds produce identical output to GitHub Actions workflow
#
# Usage:
#   make build      - Full pipeline (download → enrich → normalize → lint → merge)
#   make clean      - Remove generated files
#   make install    - Install dependencies
#   make download   - Download specs only
#   make enrich     - Enrich specs only
#   make normalize  - Normalize specs only
#   make lint       - Lint specs only
#   make merge      - Merge specs only
#   make validate   - Validate with live API (requires credentials)
#   make serve      - Serve docs locally
#
# The pipeline ensures deterministic output:
#   - specs/original/   → READ-ONLY source from F5
#   - specs/enriched/   → Branding, acronyms, grammar
#   - specs/normalized/ → Fixed $refs, cleaned operations
#   - specs/merged/     → Combined by domain + master spec
#   - docs/specs/merged → Copy for GitHub Pages

.PHONY: all build clean install download enrich normalize lint merge validate serve help check-deps

# Default target
all: build

# Full pipeline - matches GitHub Actions workflow exactly
build: check-deps download enrich normalize lint merge copy-docs
	@echo ""
	@echo "Build complete. Output in:"
	@echo "  specs/merged/     - Merged API specifications"
	@echo "  docs/specs/merged - Copy for GitHub Pages"
	@echo ""
	@echo "Run 'make serve' to preview locally"

# Check dependencies are installed
check-deps:
	@command -v python3 >/dev/null 2>&1 || { echo "Python 3 is required but not installed."; exit 1; }
	@command -v spectral >/dev/null 2>&1 || { echo "Spectral is required. Install with: npm install -g @stoplight/spectral-cli"; exit 1; }
	@python3 -c "import rich" 2>/dev/null || { echo "Python dependencies missing. Run: make install"; exit 1; }

# Install all dependencies
install:
	pip install -r requirements.txt
	npm install -g @stoplight/spectral-cli
	@echo "Dependencies installed successfully"

# Download specifications from F5 (with ETag caching)
download:
	python3 -m scripts.download --force

# Enrich specifications (branding, acronyms, grammar)
enrich:
	python3 -m scripts.enrich

# Normalize specifications (fix $refs, remove empty operations)
normalize:
	python3 -m scripts.normalize

# Lint specifications with Spectral
lint:
	python3 -m scripts.lint || true

# Merge specifications by domain
merge:
	python3 -m scripts.merge_specs

# Copy merged specs to docs folder for GitHub Pages
copy-docs:
	@mkdir -p docs/specs
	@rm -rf docs/specs/merged
	cp -r specs/merged docs/specs/

# Validate specifications with live API (optional, requires credentials)
validate:
	@if [ -z "$$F5XC_API_TOKEN" ]; then \
		echo "F5XC_API_TOKEN not set. Skipping live validation."; \
	else \
		python3 -m scripts.validate --dry-run; \
	fi

# Serve documentation locally
serve:
	@echo "Starting local server at http://localhost:8000"
	@echo "Scalar UI: http://localhost:8000/scalar/"
	@echo "Swagger UI: http://localhost:8000/swagger-ui/"
	@echo "Press Ctrl+C to stop"
	@cd docs && python3 -m http.server 8000

# Clean generated files (preserves original specs)
clean:
	rm -rf specs/enriched
	rm -rf specs/normalized
	rm -rf specs/merged
	rm -rf reports
	rm -rf docs/specs/merged
	@echo "Cleaned generated files. Original specs preserved."

# Deep clean - removes everything including downloaded specs
clean-all: clean
	rm -rf specs/original
	rm -f .etag
	rm -f .version
	@echo "Deep clean complete. Run 'make download' to fetch specs."

# Quick rebuild - skip download
rebuild: enrich normalize lint merge copy-docs

# Help
help:
	@echo "F5 XC API Enrichment Pipeline"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Main targets:"
	@echo "  build       Full pipeline (download → enrich → normalize → lint → merge)"
	@echo "  rebuild     Quick rebuild (skip download, use existing original specs)"
	@echo "  serve       Start local server to preview docs"
	@echo "  clean       Remove generated files (keeps original specs)"
	@echo "  clean-all   Remove all generated files including downloads"
	@echo ""
	@echo "Individual steps:"
	@echo "  download    Download specs from F5"
	@echo "  enrich      Apply branding, acronyms, grammar"
	@echo "  normalize   Fix orphan refs, clean operations"
	@echo "  lint        Validate with Spectral"
	@echo "  merge       Combine specs by domain"
	@echo "  validate    Test with live API (needs credentials)"
	@echo ""
	@echo "Setup:"
	@echo "  install     Install Python and Node.js dependencies"
	@echo "  check-deps  Verify all dependencies are installed"

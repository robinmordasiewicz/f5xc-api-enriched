# Development Guide - F5 XC API Enriched

This guide provides everything you need to work with the F5 XC API Enrichment Pipeline.

## Table of Contents

- [Quick Start](#quick-start)
- [Architecture Overview](#architecture-overview)
- [Workflow Patterns](#workflow-patterns)
- [Discovery Deep Dive](#discovery-deep-dive)
- [Release Process](#release-process)
- [Configuration Guide](#configuration-guide)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

---

## Quick Start

### First-Time Setup (5 minutes)

```bash
# Clone the repository
git clone https://github.com/robinmordasiewicz/f5xc-api-enriched.git
cd f5xc-api-enriched

# Create virtual environment and install dependencies
make install

# Install pre-commit hooks
make pre-commit-install

# Download specs and run pipeline
make build

# Preview documentation locally
make serve
# Open: http://localhost:8000/scalar/
```

### Daily Development

```bash
# Quick rebuild (uses cached specs)
make rebuild

# Run all quality checks
make pre-commit-run

# Preview documentation
make serve
```

---

## Architecture Overview

### Two-Folder Design

The pipeline uses a simple two-folder architecture:

```text
┌─────────────────────┐     ┌─────────────────────────────┐
│   specs/original/   │────▶│   docs/specifications/api/  │
│   (READ-ONLY)       │     │   (GENERATED)               │
│   - Downloaded      │     │   - Domain specs            │
│   - Gitignored      │     │   - Master spec             │
│   - ETag cached     │     │   - GitHub Pages            │
└─────────────────────┘     └─────────────────────────────┘
```

### Pipeline Flow

```text
Download (ETag) → Enrich → Normalize → Merge → Lint → Serve
     │              │          │         │       │
     ▼              ▼          ▼         ▼       ▼
 270 specs     Branding    Fix refs   23 domains  Spectral
             + Grammar    + Types    + Master     rules
```

### Directory Structure

| Directory | Purpose | Git Status |
|-----------|---------|------------|
| `specs/original/` | F5 source specs | Gitignored |
| `specs/discovered/` | API discovery output | Tracked (openapi.json, session.json) |
| `docs/specifications/api/` | Generated domain specs | Gitignored |
| `docs/scalar/` | Scalar UI | Tracked |
| `docs/swagger-ui/` | Swagger UI | Tracked |
| `scripts/` | Python pipeline scripts | Tracked |
| `config/` | Pipeline configuration | Tracked |
| `reports/` | Generated reports | Gitignored |

---

## Workflow Patterns

### 1. Discovery Workflow

**When to Use**: Periodically to capture real API behavior.

**Prerequisites**:

- VPN connection to F5 XC environment
- Valid API credentials

```bash
# Set credentials
export F5XC_API_URL="https://your-tenant.console.ves.volterra.io/api"
export F5XC_API_TOKEN="your-api-token"

# Run discovery (5-10 minutes)
make discover

# View results
jq '.statistics' specs/discovered/session.json

# Commit for CI/CD
make push-discovery
```

**What Discovery Captures**:

- Actual required/optional fields
- Enum values from live responses
- Default values
- Pattern validations
- Response examples

### 2. Release Workflow

**How Releases Happen** (Automated):

1. Daily schedule (6 AM UTC) or push to main triggers workflow
2. ETag check determines if F5 specs changed
3. Pipeline processes and enriches specs
4. Version auto-incremented based on changes
5. GitHub Release created with changelog
6. Documentation deployed to GitHub Pages

**Version Bump Rules**:

| Condition | Bump Type | Example |
|-----------|-----------|---------|
| `[major]` in commit | Major | 1.0.0 → 2.0.0 |
| `BREAKING CHANGE` in commit | Major | 1.0.0 → 2.0.0 |
| New domain spec added | Minor | 1.0.0 → 1.1.0 |
| Any other change | Patch | 1.0.0 → 1.0.1 |

### 3. Development Workflow

**Making Changes**:

```bash
# Create feature branch
git checkout -b feature/my-change

# Make changes to config or scripts
# ...

# Test locally
make pipeline
make lint

# Commit (pre-commit hooks run automatically)
git add .
git commit -m "feat: add new enrichment rule"

# Push and create PR
git push -u origin feature/my-change
gh pr create
```

---

## Discovery Deep Dive

### What is Discovery?

Discovery explores the live F5 XC API to find:

- **Undocumented constraints**: Required fields not marked in OpenAPI
- **Actual enum values**: Real values seen in production
- **Default behaviors**: What happens when fields are omitted
- **Response patterns**: Actual data shapes

### Discovery Configuration

```yaml
# config/discovery.yaml
discovery:
  exploration:
    namespaces:
      - "system"
      - "shared"
    methods:
      - "GET"
      - "OPTIONS"
    max_endpoints_per_run: 500

  schema_inference:
    sample_size: 3
    detect_patterns: true
    detect_constraints: true
```

### Discovery Extensions

Discovery adds `x-discovered-*` extensions to specs:

```json
{
  "properties": {
    "name": {
      "type": "string",
      "x-discovered-required": true,
      "x-discovered-pattern": "^[a-z][a-z0-9-]*$",
      "x-discovered-examples": ["my-app", "prod-lb"]
    }
  }
}
```

### Constraint Analysis Report

After discovery, generate a comparison report:

```bash
make constraint-report
# Output: reports/constraint-analysis.md
```

This shows differences between published specs and actual API behavior.

---

## Release Process

### Automatic Releases

Releases are fully automated. The workflow:

1. Detects spec changes via ETag
2. Runs full enrichment pipeline
3. Calculates version bump
4. Generates changelog
5. Creates GitHub Release
6. Deploys to GitHub Pages

### Release Package Contents

```text
f5xc-api-specs-v1.0.14.zip
├── openapi.json       # Master combined spec
├── openapi.yaml       # YAML format
├── domains/           # Individual domain specs
│   ├── api_security.json
│   ├── load_balancer.json
│   └── ...
├── index.json         # Metadata
├── CHANGELOG.md       # Release notes
└── README.md          # Usage instructions
```

### Manual Workflow Trigger

If you need to force a release:

```bash
gh workflow run sync-and-enrich.yml
gh run watch
```

---

## Configuration Guide

### Enrichment Configuration

```yaml
# config/enrichment.yaml
enrichment:
  branding:
    replacements:
      "Volterra": "F5 Distributed Cloud"
      "VES": "F5 XC"

  acronyms:
    API: "Application Programming Interface"
    DNS: "Domain Name System"
    # 100+ more...

  grammar:
    enabled: true
    language_tool: true
```

### Normalization Configuration

```yaml
# config/normalization.yaml
normalization:
  orphan_refs:
    fix: true
    remove_if_unresolvable: true

  empty_operations:
    remove: true

  type_standardization:
    enabled: true
```

### Spectral Linting Rules

```yaml
# config/spectral.yaml
extends:
  - spectral:oas

rules:
  operation-operationId: error
  operation-tags: warn
  # Custom rules...
```

---

## Troubleshooting

### Issue 1: Pre-commit Takes Too Long

**Symptoms**: Commits take 50+ seconds.

**Cause**: Pipeline runs on every commit to ensure consistency.

**Solution**: This is intentional. If you need faster commits during development:

```bash
git commit --no-verify -m "WIP: work in progress"
# Remember to run: make pre-commit-run before final commit
```

### Issue 2: Discovery Fails

**Symptoms**: `make discover` returns connection errors.

**Diagnosis**:

```bash
# Check VPN
ping your-tenant.console.ves.volterra.io

# Check credentials
echo $F5XC_API_TOKEN | head -c 10

# Check API URL format
echo $F5XC_API_URL
# Should be: https://tenant.console.ves.volterra.io/api
```

**Solution**: Ensure VPN is connected and credentials are valid.

### Issue 3: Lint Errors on Generated Specs

**Symptoms**: `make lint` fails with Spectral errors.

**Diagnosis**:

```bash
# Check lint report
cat reports/lint-report.json | jq '.errors'
```

**Solution**: Fix issues in enrichment/normalization config, not the output files.

### Issue 4: Version Conflicts

**Symptoms**: Merge conflicts in `.version` file.

**Cause**: Multiple PRs touching the same version.

**Solution**:

```bash
# Accept incoming version (workflow will correct it)
git checkout --theirs .version
git add .version
git commit -m "resolve: accept workflow version"
```

### Issue 5: Missing Specs After Clone

**Symptoms**: `docs/specifications/api/` is empty.

**Cause**: Generated specs are gitignored.

**Solution**:

```bash
make build  # Downloads and generates everything
```

### Issue 6: Large File Blocked

**Symptoms**: Pre-commit fails with "exceeds X KB" error.

**Cause**: File exceeds 1MB limit.

**Solution**: If file should be tracked, add exclusion to `.pre-commit-config.yaml`:

```yaml
- id: check-added-large-files
  exclude: ^path/to/large/file\.json$
```

---

## Contributing

### Development Process

1. **Branch**: Create feature branch from `main`
2. **Develop**: Make changes with tests
3. **Validate**: Run `make pre-commit-run`
4. **Commit**: Use conventional commit messages
5. **PR**: Create pull request with description
6. **Review**: Address feedback
7. **Merge**: Squash and merge to main

### Commit Message Format

```text
type(scope): description

[optional body]

[optional footer]
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Examples:

```text
feat(enrichment): add new acronym expansions
fix(pipeline): handle empty description fields
docs(readme): update installation instructions
```

### Code Style

- **Python**: Ruff formatter + linter (configured in `pyproject.toml`)
- **YAML**: yamllint (configured in `.yamllint.yaml`)
- **Markdown**: markdownlint (configured via pre-commit)

### Testing Changes

Always test before committing:

```bash
# Full pipeline test
make pipeline

# Lint validation
make lint

# All quality checks
make pre-commit-run

# Discovery dry run (no API calls)
make discover-dry-run
```

---

## Quick Reference

### Make Targets

| Target | Description |
|--------|-------------|
| `make build` | Full build (download + pipeline) |
| `make rebuild` | Quick rebuild (skip download) |
| `make download` | Download specs (ETag cached) |
| `make download-force` | Force download |
| `make pipeline` | Run enrichment pipeline |
| `make lint` | Spectral linting |
| `make serve` | Local documentation server |
| `make discover` | API discovery (VPN required) |
| `make push-discovery` | Commit discovery data |
| `make clean` | Remove generated files |
| `make pre-commit-run` | Run all quality checks |

### Environment Variables

| Variable | Purpose |
|----------|---------|
| `F5XC_API_URL` | F5 XC tenant API URL |
| `F5XC_API_TOKEN` | API authentication token |

### Key Files

| File | Purpose |
|------|---------|
| `.version` | Current semantic version |
| `.etag` | Last downloaded ETag |
| `CHANGELOG.md` | Auto-generated changelog |
| `config/enrichment.yaml` | Enrichment rules |
| `config/normalization.yaml` | Normalization rules |
| `config/discovery.yaml` | Discovery settings |
| `config/spectral.yaml` | Linting rules |

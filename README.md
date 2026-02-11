# f5xc-api-enriched

Automated OpenAPI enrichment pipeline for F5 Distributed Cloud API specifications, enhancing developer experience with comprehensive descriptions, metadata, and standardized extensions.

## Overview

This repository transforms F5 Distributed Cloud's 270+ OpenAPI specifications into enriched, developer-friendly documentation with:

- **100% Description Coverage**: All 32,141 describable properties have meaningful descriptions
- **DRY-Compliant Content**: Pattern-based generation preventing redundant information
- **Multi-Tier Descriptions**: Short (≤60 chars), medium (≤150 chars), long (≤500 chars) for different use cases
- **Standardized Extensions**: Custom OpenAPI extensions for metadata, configuration, and tooling integration

## Key Features

### Description Enrichment

- **Property Descriptions**: 32,141 properties with full descriptions (100% coverage)
- **Short Descriptions**: 21,422 properties with CLI-optimized descriptions (37.8% coverage)
- **Domain Descriptions**: 270+ specifications with 3-tier descriptions (short/medium/long)
- **Operation Descriptions**: DRY-compliant, noun-first descriptions for API operations
- **Pattern System**: 140+ field patterns + 80+ short description patterns + 8 operation patterns

### Metadata Enrichment

- **Configuration Metadata**: Minimum configurations for 90+ resources (5 explicit + auto-generated)
- **Operation Metadata**: Danger levels, required fields, side effects for all operations
- **Resource Metadata**: Rich metadata for tooling integration
- **Best Practices**: Domain-specific operational knowledge and guided workflows
- **Acronym Expansion**: 450+ industry acronyms and F5-specific terminology

### Quality & Validation

- **99% Meaningful Descriptions**: Not generic fallbacks
- **DRY Compliance**: 5-layer validation preventing redundant content
- **Character Limits**: Enforced limits for each description tier
- **Grammar Enhancement**: Automated grammar correction for technical writing
- **Consistency Validation**: Cross-specification validation

## Architecture

### Pipeline Stages

```text
1. Download    → GitHub Releases (version-cached spec retrieval)
2. Enrich      → Descriptions, branding, grammar, metadata
3. Normalize   → Schema references, type fixes, consistency
4. Merge       → Domain-specific spec generation
5. Validate    → Spectral linting + live API validation
6. Deploy      → GitHub Pages (Starlight docs)
```

### Enrichment Pipeline (17 Steps)

| Step | Enricher | Purpose |
|------|----------|---------|
| 1 | SchemaFixer | Fix invalid schemas and missing components |
| 2 | BrandingTransformer | Branding consistency |
| 3 | TagGenerator | Generate operation tags from paths |
| 4 | DescriptionEnricher | Domain descriptions (short/medium/long) |
| 5 | FieldDescriptionEnricher | Property descriptions (140+ patterns) |
| 6 | GrammarImprover | Automated grammar correction |
| 7 | DescriptionValidator | DRY compliance, quality validation |
| 8 | DescriptionStructureTransformer | Convert block quotes to proper structure |
| 9 | AcronymEnricher | Add acronym definitions to specs |
| 10 | PropertyDescriptionShortEnricher | CLI-optimized short descriptions (80+ patterns) |
| 11 | ResourceExamplesEnricher | Add tiered resource examples |
| 12 | FieldMetadataEnricher | Add field-level metadata |
| 13 | ValidationEnricher | Add validation rules and patterns |
| 14 | **OperationDescriptionEnricher** | **DRY-compliant operation descriptions** |
| 15 | OperationMetadataEnricher | Danger levels, required fields, side effects |
| 16 | MinimumConfigurationEnricher | Minimum viable configurations |
| 17 | ReadOnlyEnricher | Mark API-computed fields as readOnly |

### Discovery & Reconciliation (VPN Required)

Live API exploration to discover undocumented behavior:

```bash
export F5XC_API_URL="https://tenant.console.ves.volterra.io/api"
export F5XC_API_TOKEN="your-api-token"
make discover              # Explore live API
make push-discovery        # Commit discovery data for CI/CD
```

**Discovery Features**:

- Tighter constraints detection (e.g., API enforces maxLength:63 vs spec allows 1024)
- New undocumented constraints (pattern validation, enum restrictions)
- Response time profiling (p50/p95/p99 latencies)
- Rate limiting behavior
- Undocumented fields

### GitHub Release Integration

API specifications are sourced from **[robinmordasiewicz/f5xc-api-fixed](https://github.com/robinmordasiewicz/f5xc-api-fixed)** via GitHub Releases.

**Benefits**:
- Pre-validated specs (268 domain specs, 5.7 MB compressed)
- Version-based caching (faster than HTTP ETag)
- Full control via source repository
- Easy rollback to any release

**Authentication** (optional but recommended):
```bash
# Set GitHub token for higher rate limits (5000/hr vs 60/hr)
export GITHUB_TOKEN="ghp_your_personal_access_token"
```

**Release Format**:
- Versioning: `vYYYY.MM.DD-N` (date-based with sequence)
- Asset: `f5xc-api-fixed-v{version}.zip`
- Contents: `domains/*.json` (268 domain specifications)

**CI/CD**: GitHub Actions automatically uses `secrets.GITHUB_TOKEN` for authentication.

## Quick Start

### Prerequisites

```bash
# Python 3.11+ required
python --version

# Install dependencies
make install

# Install pre-commit hooks (runs full pipeline on every commit)
make pre-commit-install
```

### Basic Usage

```bash
# Full pipeline (download → enrich → normalize → merge)
make build

# Quick rebuild (skip download, use existing specs)
make rebuild

# Individual stages
make download       # Fetch latest F5 specs from GitHub Releases (version cached)
make pipeline       # Run enrichment pipeline
make lint           # Spectral OpenAPI linting
make validate       # Test curl examples against live API

# Development
make serve          # Serve docs locally (http://localhost:8000)
make clean          # Remove generated files
```

### CI/CD Integration

The repository uses GitHub Actions for automated releases:

```yaml
Trigger: Daily schedule, push to main, manual dispatch
Process:
  1. Check for spec updates (GitHub release version comparison)
  2. Download changed specs
  3. Run enrichment pipeline
  4. Validate with Spectral + live API
  5. Auto-version (semantic versioning)
  6. Create GitHub release
  7. Deploy to GitHub Pages
```

**Version Bumping**:

- New API domains → **Minor** version (e.g., 1.0.15 → 1.1.0)
- Spec updates (no new domains) → **Patch** version (e.g., 1.0.15 → 1.0.16)
- Pipeline/config changes → **Patch** version
- Breaking changes → **Major** version (commit message: `[major]` or `BREAKING CHANGE`)

## Operation Description System

### Problem: Redundant Descriptions

**Before** (verb-first, redundant):

```yaml
# Command: <tool> <domain> create <resource>
x-f5xc-operation-metadata:
  purpose: "Create new http_loadbalancer"  # ❌ Redundant - user typed "create"
```

**After** (noun-first, DRY-compliant):

```yaml
# Command: <tool> <domain> create <resource>
x-f5xc-operation-metadata:
  purpose: "HTTP/HTTPS load balancer with origin pools and routing rules"  # ✅
```

### Three-Tier Matching Strategy

```text
1. Exact Match: "http_loadbalancer" → explicit description
2. Pattern Match: ".*loadbalancer.*" → pattern-based description
3. Method Fallback: POST → "Resource creation operation"
```

### Configuration

`config/operation_descriptions.yaml`:

- 10 high-priority resources (explicit descriptions)
- 8 pattern matchers (regex-based matching)
- 5 HTTP method fallbacks (POST/GET/PUT/PATCH/DELETE)

## Using Enriched Specifications

### Accessing Extensions

The enriched specifications include custom OpenAPI extensions in the `x-f5xc-*` namespace. These extensions provide metadata for building tools, CLI interfaces, and AI assistants.

#### Operation Metadata

Access operation-level metadata for command interfaces:

```javascript
// JavaScript/TypeScript example
const operation = spec.paths["/api/config/namespaces/{namespace}/http_loadbalancers"]["post"];
const metadata = operation["x-f5xc-operation-metadata"];

console.log(metadata.purpose);          // "HTTP/HTTPS load balancer with origin pools..."
console.log(metadata.danger_level);     // "medium"
console.log(metadata.required_fields);  // ["metadata.name", "metadata.namespace"]
```

```python
# Python example
operation = spec["paths"]["/api/config/namespaces/{namespace}/http_loadbalancers"]["post"]
metadata = operation.get("x-f5xc-operation-metadata", {})

print(metadata.get("purpose"))          # "HTTP/HTTPS load balancer with origin pools..."
print(metadata.get("danger_level"))     # "medium"
print(metadata.get("required_fields"))  # ["metadata.name", "metadata.namespace"]
```

#### Minimum Configurations

Access minimum viable configurations for resource creation:

```javascript
// JavaScript/TypeScript example
const schema = spec.components.schemas["HttpLoadBalancerCreateRequest"];
const minConfig = schema["x-f5xc-minimum-configuration"];

console.log(minConfig.description);     // Minimum configuration description
console.log(minConfig.required_fields); // ["metadata.name", "metadata.namespace"]
console.log(minConfig.example_yaml);    // YAML configuration template
```

```python
# Python example
schema = spec["components"]["schemas"]["HttpLoadBalancerCreateRequest"]
min_config = schema.get("x-f5xc-minimum-configuration", {})

print(min_config.get("description"))     # Minimum configuration description
print(min_config.get("required_fields")) # ["metadata.name", "metadata.namespace"]
print(min_config.get("example_yaml"))    # YAML configuration template
```

#### Resource Metadata

Access rich resource metadata from the specification index:

```javascript
// JavaScript/TypeScript example
const index = await fetch("https://robinmordasiewicz.github.io/f5xc-api-enriched/specifications/index.json");
const data = await index.json();

const resource = data.primary_resources.find(r => r.name === "http_loadbalancer");
console.log(resource.description);       // Full resource description
console.log(resource.tier);              // "Standard"
console.log(resource.dependencies);      // {required: ["origin_pool"], optional: [...]}
```

```python
# Python example
import requests

response = requests.get("https://robinmordasiewicz.github.io/f5xc-api-enriched/specifications/index.json")
data = response.json()

resource = next(r for r in data["primary_resources"] if r["name"] == "http_loadbalancer")
print(resource["description"])       # Full resource description
print(resource["tier"])              # "Standard"
print(resource["dependencies"])      # {required: ["origin_pool"], optional: [...]}
```

### Multi-Tier Descriptions

Specifications include three description tiers optimized for different use cases:

| Tier | Max Length | Use Case | Access Path |
|------|-----------|----------|-------------|
| `short` | 60 chars | CLI columns, tooltips | `property["x-f5xc-description-short"]` |
| `medium` | 150 chars | Help text, summaries | `spec.info["x-f5xc-description-medium"]` |
| `long` | 500 chars | Documentation, AI context | `property.description` |

```javascript
// Accessing description tiers
const property = schema.properties["origin_pool"];

// Short (CLI display)
const shortDesc = property["x-f5xc-description-short"];  // "Backend server pool"

// Long (full documentation)
const longDesc = property.description;  // "Origin pool defines a collection of backend..."
```

## Documentation

### Published Documentation

- **API Specs Index**: <https://robinmordasiewicz.github.io/f5xc-api-enriched/>

### Developer Documentation

- **CLAUDE.md**: Comprehensive AI assistant instructions and technical details
- **CHANGELOG.md**: Auto-generated release notes

## Configuration Files and Extensions

### Key Configuration Files

| File | Purpose |
|------|---------|
| `config/enrichment.yaml` | Branding, acronyms, grammar rules |
| `config/normalization.yaml` | Schema normalization rules |
| `config/domain_descriptions.yaml` | Domain descriptions (3 tiers) |
| `config/operation_descriptions.yaml` | Operation descriptions (DRY-compliant) |
| `config/field_descriptions.yaml` | Field description patterns (140+) |
| `config/property_description_short.yaml` | Short description patterns (80+) |
| `config/minimum_configs.yaml` | Minimum viable configurations |
| `config/resource_metadata.yaml` | Per-resource metadata (90+ resources) |
| `config/extension_registry.yaml` | All x-f5xc-* extensions (50+) |

### Extension Namespace

All custom extensions use the `x-f5xc-*` namespace:

- **Spec-level**: `x-f5xc-cli-domain`, `x-f5xc-enriched-version`, `x-f5xc-glossary`
- **Schema-level**: `x-f5xc-minimum-configuration`, `x-f5xc-display-name`, `x-f5xc-namespace-scope`
- **Property-level**: `x-f5xc-description-short`, `x-f5xc-validation`, `x-f5xc-examples`
- **Operation-level**: `x-f5xc-operation-metadata`, `x-f5xc-danger-level`, `x-f5xc-required-fields`

See `config/extension_registry.yaml` for complete documentation.

## Multi-Environment Support

The specifications support multi-environment, multi-tenant deployments through server variables:

```yaml
servers:
  - url: https://{tenant}.{console_url}/api/v1/namespaces/{namespace}
    variables:
      tenant: {default: "example-corp"}
      console_url: {default: "console.ves.volterra.io"}
      namespace: {default: "default"}
```

**Environment Variables**:

- `F5XC_TENANT`: Tenant identifier
- `F5XC_CONSOLE_URL`: Console URL base
- `F5XC_DEFAULT_NAMESPACE`: Default namespace
- `F5XC_ENVIRONMENT`: Environment designation (production/staging/development)
- `F5XC_REGION`: Geographic region
- `F5XC_DOMAIN_PREFIX`: Domain naming convention

## Statistics

### Coverage Metrics

```text
Total Specifications: 270
Total Properties: 56,706
Properties with Descriptions: 32,141 (56.7% - 100% of describable)
Properties with Short Descriptions: 21,422 (37.8%)
$ref Properties: 24,565 (appropriately excluded)
Quality Score: 99% meaningful descriptions
```

### Pipeline Performance

```text
Average Processing Time: ~2 minutes (270 specs)
Peak Memory Usage: 154 MB
Cache Hit Rate: ~85% (GitHub release version-based)
Parallel Batch Processing: 14 batches
Discovery Enrichment: 1,239,194 constraints reconciled
```

## Development

### Running Tests

```bash
# All tests
pytest

# Specific test suites
pytest tests/test_operation_description_enricher.py -v
pytest tests/test_deprecated_tier_enricher.py -v

# With coverage
pytest --cov=scripts --cov-report=html
```

### Pre-commit Hooks

The repository uses pre-commit hooks that run on every commit:

```yaml
Hooks:
  - F5 XC API Enrichment Pipeline (full rebuild)
  - Spectral linting (all 270+ specs)
  - Ruff (linting + formatting)
  - MyPy (type checking)
  - Security checks (gitleaks, detect-private-key)
  - File hygiene (trailing whitespace, line endings)
```

**Note**: Every commit triggers a full pipeline run (~50 seconds). This ensures specification consistency.

### Contributing

1. Create feature branch: `git checkout -b feature/issue-XXX-description`
2. Make changes
3. Commit (pre-commit hooks will run automatically)
4. Push and create PR
5. CI/CD will validate and auto-merge if approved

## License

MIT License - Copyright (c) 2026 Robin Mordasiewicz

## Support

- **Issues**: [GitHub Issues](https://github.com/robinmordasiewicz/f5xc-api-enriched/issues)
- **Discussions**: [GitHub Discussions](https://github.com/robinmordasiewicz/f5xc-api-enriched/discussions)

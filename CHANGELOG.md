# Changelog

## Version 2025.12.19 (2025-12-19)

### Changes

- Updated API specifications from F5 Distributed Cloud
- Applied enrichment pipeline:
  - Acronym normalization (100+ terms)
  - Grammar improvements
  - Branding updates (Volterra → F5 Distributed Cloud)
- Applied normalization pipeline:
  - Fixed orphan $ref references
  - Removed empty operations
  - Type standardization
- Validated with Spectral OpenAPI linter
- Merged specifications by domain

### Statistics

- Original specs: 270
- Processed specs: 0
- Domains: 20

### Output Structure

```text
specs/
├── original/              # READ-ONLY source from F5
└── enriched/              # Single output folder
    ├── individual/        # 270 processed specs
    ├── load_balancer.json
    ├── security.json
    ├── networking.json
    ├── infrastructure.json
    ├── identity.json
    ├── observability.json
    ├── config.json
    ├── other.json
    ├── openapi.json       # Master combined spec
    └── index.json         # Metadata index
```

### Source

- Source: F5 Distributed Cloud OpenAPI specifications
- ETag: N/A

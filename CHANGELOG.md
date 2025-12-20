# Changelog

## Version 1.0.12 (2025-12-20)

### Release Type

- **patch** release

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
- Domains: 23
- Total paths: 1553
- Total schemas: 8014

### Output Structure

```text
docs/specifications/api/
├── [domain].json        # Domain-specific specs
├── openapi.json         # Master combined spec
└── index.json           # Metadata index
```

### Source

- Source: F5 Distributed Cloud OpenAPI specifications
- ETag: N/A

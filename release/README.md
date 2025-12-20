# F5 Distributed Cloud API Specifications

Enriched OpenAPI 3.0 specifications for F5 Distributed Cloud (XC) platform.

## Quick Start

### Validate the Specification

```bash
npx @redocly/cli lint openapi.json
```

### Generate a Python Client

```bash
npx @openapitools/openapi-generator-cli generate \
  -i openapi.json -g python -o ./python-client
```

### Generate a Go Client

```bash
npx @openapitools/openapi-generator-cli generate \
  -i openapi.json -g go -o ./go-client
```

### Import to Postman

1. Open Postman
2. Click **Import** → **File**
3. Select `openapi.json` or any domain-specific spec from `domains/`

### Import to Insomnia

1. Open Insomnia
2. Click **Import/Export** → **Import Data**
3. Select `openapi.json`

## Contents

| File | Description |
|------|-------------|
| `openapi.json` | Master specification (all domains combined) |
| `openapi.yaml` | Master specification in YAML format |
| `index.json` | Metadata and inventory of all specifications |
| `domains/` | Individual domain specifications for selective import |

## Domain Specifications

The `domains/` directory contains individual specifications organized by functional area:

| Domain | Description |
|--------|-------------|
| `api_security.json` | API security and protection features |
| `applications.json` | Application delivery and management |
| `bigip.json` | BIG-IP integration and management |
| `billing.json` | Billing and usage tracking |
| `cdn.json` | Content delivery network configuration |
| `config.json` | Configuration management |
| `identity.json` | Identity and access management |
| `infrastructure.json` | Infrastructure provisioning |
| `infrastructure_protection.json` | DDoS and infrastructure protection |
| `integrations.json` | Third-party integrations |
| `load_balancer.json` | Load balancing configuration |
| `networking.json` | Network connectivity and routing |
| `nginx.json` | NGINX management |
| `observability.json` | Monitoring, logging, and metrics |
| `operations.json` | Operational tasks and automation |
| `security.json` | Security policies and WAF |
| `service_mesh.json` | Service mesh configuration |
| `shape_security.json` | Bot defense and fraud protection |
| `subscriptions.json` | Subscription management |
| `tenant_management.json` | Multi-tenant administration |
| `vpn.json` | VPN and secure connectivity |

## Version Information

- **Version**: {VERSION}
- **Release Date**: {DATE}
- **OpenAPI Version**: 3.0.3

## Enrichment Applied

These specifications have been enriched with:

- **Acronym Normalization**: 100+ technical terms standardized
- **Grammar Improvements**: Enhanced descriptions and summaries
- **Branding Updates**: Volterra references updated to F5 Distributed Cloud
- **Schema Validation**: All specifications validated with Spectral linter

## Usage Tips

### Working with Large Specs

The master `openapi.json` is comprehensive (~18MB). For faster tooling:

```bash
# Use a specific domain instead of the full spec
npx @openapitools/openapi-generator-cli generate \
  -i domains/load_balancer.json -g python -o ./lb-client
```

### Bundling for Distribution

```bash
npx @redocly/cli bundle openapi.json -o bundled-openapi.json
```

### Converting Formats

```bash
# JSON to YAML (already included as openapi.yaml)
npx @redocly/cli bundle openapi.json -o openapi.yaml

# Split into multiple files
npx @redocly/cli split openapi.json --outDir ./split-specs
```

## Legal Notice

These API specifications are derived from F5 Distributed Cloud's publicly
available OpenAPI documentation. The underlying API specification content
is the intellectual property of F5, Inc.

This enriched version includes automated improvements such as grammar
corrections, acronym normalization, and branding updates. These enrichments
are provided as-is for developer convenience.

For official API documentation and terms of use, please refer to:

- [F5 Distributed Cloud Documentation](https://docs.cloud.f5.com/)
- [F5 Terms of Service](https://www.f5.com/company/policies/terms-of-service)

## Source

- **Repository**: [f5xc-api-enriched](https://github.com/robinmordasiewicz/f5xc-api-enriched)
- **Documentation**: [GitHub Pages](https://robinmordasiewicz.github.io/f5xc-api-enriched/)

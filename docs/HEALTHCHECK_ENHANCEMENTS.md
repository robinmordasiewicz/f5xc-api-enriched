# Healthcheck Schema Enrichments

This document describes the enrichment metadata applied to healthcheck-related schemas in the F5 XC API specifications.

## Overview

The enriched specifications contain two categories of default value metadata:

| Extension | Meaning | Implication |
|-----------|---------|-------------|
| `x-f5xc-server-default` | The F5 XC API server applies this value when the field is omitted | Field is optional; omitting it produces the documented default behavior |
| `x-f5xc-recommended-value` | The F5 XC web console pre-populates this value for new resources | Field has no server default but this value represents typical configuration |

**Key distinction**: Server-applied defaults are handled by the API automatically. Recommended values are suggestions that require explicit inclusion if desired.

## Enriched Schemas

### Pattern

All schemas matching `healthcheck.*SpecType` receive enrichments:

- `healthcheckCreateSpecType`
- `healthcheckReplaceSpecType`
- `healthcheckGetSpecType`

Additionally, the nested schema `healthcheckHttpHealthCheck` contains enrichments for HTTP health check configuration.

## Server-Applied Defaults

Fields marked with `x-f5xc-server-default: true` have their `default` value applied by the F5 XC API server when omitted from requests. These fields are effectively optional—the API produces consistent behavior whether the field is explicitly set to the default value or omitted entirely.

### Top-Level Fields

| Field | Default Value | Type | Description |
|-------|---------------|------|-------------|
| `jitter` | `0` | integer | Absolute jitter value for timing randomization |
| `jitter_percent` | `0` | integer | Percentage-based jitter for timing randomization |

### healthcheckHttpHealthCheck Schema

| Field | Default Value | Type | Description |
|-------|---------------|------|-------------|
| `use_origin_server_name` | `{}` | object | Origin server name for Host header |
| `headers` | `{}` | object | Custom headers |
| `request_headers_to_remove` | `[]` | array | Headers to strip from requests |
| `use_http2` | `false` | boolean | HTTP/2 support |
| `expected_status_codes` | `[]` | array | Accepted status codes (empty = 200-299) |

## Recommended Values

Fields marked with `x-f5xc-recommended-value` indicate values that the F5 XC web console pre-populates when creating new resources. Unlike server-applied defaults, these values are not automatically applied by the API—they represent typical configurations that align with console behavior. These values are derived from F5 XC UI observation and provide a baseline for generating configurations that match console-created resources.

### Top-Level Fields

| Field | Recommended Value | Type | Description |
|-------|-------------------|------|-------------|
| `timeout` | `3` | integer | Health check timeout in seconds |
| `interval` | `15` | integer | Interval between health checks in seconds |
| `unhealthy_threshold` | `1` | integer | Consecutive failures before marking unhealthy |
| `healthy_threshold` | `3` | integer | Consecutive successes before marking healthy |
| `jitter_percent` | `30` | integer | Jitter percentage for production use |

### healthcheckHttpHealthCheck Schema

| Field | Recommended Value | Type | Description |
|-------|-------------------|------|-------------|
| `path` | `"/"` | string | Health check endpoint path |
| `use_http2` | `false` | boolean | HTTP/2 support setting |
| `expected_status_codes` | `["200"]` | array | Status codes indicating healthy origin |
| `use_origin_server_name` | `{}` | object | Origin server name for Host header |

## OneOf Variant Recommendations

Schemas containing mutually exclusive field groups (OneOf) include `x-f5xc-recommended-oneof-variant` to indicate which variant is most commonly used. This metadata identifies the typical choice when multiple options exist, based on F5 XC console defaults and common usage patterns.

| Schema | OneOf Group | Recommended Variant | Description |
|--------|-------------|---------------------|-------------|
| `healthcheckCreateSpecType` | `health_check` | `http_health_check` | HTTP health check type |
| `healthcheckReplaceSpecType` | `health_check` | `http_health_check` | HTTP health check type |

## OpenAPI Extensions Reference

These vendor extensions are added to the standard OpenAPI schema to convey F5 XC-specific default behavior.

### x-f5xc-server-default

**Type**: `boolean`

When `true`, indicates the accompanying `default` value is enforced by the F5 XC API server. Fields with this extension can be safely omitted from API requests—the server applies the default automatically.

```yaml
use_http2:
  type: boolean
  default: false
  x-f5xc-server-default: true
```

### x-f5xc-recommended-value

**Type**: `any` (matches field type)

Specifies a value that the F5 XC web console uses as a pre-populated default. This value is not server-enforced but represents the typical starting configuration for new resources created via the console.

```yaml
timeout:
  type: integer
  x-f5xc-recommended-value: 3
```

### x-f5xc-recommended-oneof-variant

**Type**: `object` (map of group name to variant name)

For schemas with mutually exclusive field groups, identifies which variant is the default or most common choice. The key is the OneOf group name and the value is the recommended variant field name.

```yaml
healthcheckCreateSpecType:
  type: object
  x-f5xc-recommended-oneof-variant:
    health_check: "http_health_check"
```

## Data Access

### OpenAPI Specifications

Enriched schemas are located in:

| File | Content |
|------|---------|
| `docs/specifications/api/virtual.json` | `healthcheckHttpHealthCheck`, `healthcheckCreateSpecType`, `healthcheckReplaceSpecType`, `healthcheckGetSpecType` |
| `docs/specifications/api/openapi.json` | Merged specification with all schemas |

### validation.json Structure

Healthcheck defaults are consolidated at:

```
defaults.resources.healthcheck
├── server_applied      # Fields with x-f5xc-server-default: true
├── recommended         # Fields with x-f5xc-recommended-value
├── oneof_recommended   # OneOf variant recommendations
└── nested_recommended  # Nested schema recommended values
```

## Related Documentation

- [Validation Specification](VALIDATION_SPEC.md) - validation.json format and structure
- [Origin Pool Enhancements](ORIGINPOOL_ENHANCEMENTS.md) - Origin pool schema enrichments
- [Minimum Configuration](/config/minimum_configs.yaml) - Resource configuration definitions

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 2.1.2 | 2026-01-18 | Rewritten as pure API reference; removed downstream examples and prescriptive language |
| 2.1.1 | 2026-01-18 | Added nested recommended values, OneOf recommended variants, `x-f5xc-recommended-oneof-variant` extension |
| 2.1.0 | 2026-01-18 | Added unified defaults structure in validation.json |
| 2.0.30 | 2026-01-16 | Added nested defaults for `$ref` schemas (healthcheckHttpHealthCheck) |
| 2.0.29 | 2026-01-17 | Initial healthcheck defaults |

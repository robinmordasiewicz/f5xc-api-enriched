# Healthcheck Schema Enrichments

Enrichment metadata for healthcheck-related schemas. See [OpenAPI Extensions](DEVELOPMENT.md#openapi-extensions) for extension definitions.

## Enriched Schemas

### Pattern

All schemas matching `healthcheck.*SpecType` receive enrichments:

- `healthcheckCreateSpecType`
- `healthcheckReplaceSpecType`
- `healthcheckGetSpecType`

Additionally, the nested schema `healthcheckHttpHealthCheck` contains enrichments for HTTP health check configuration.

## Server-Applied Defaults

Fields marked with `x-f5xc-server-default: true` have their `default` value applied by the F5 XC API server when omitted from requests.

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

Fields marked with `x-f5xc-recommended-value` indicate values that the F5 XC web console pre-populates when creating new resources.

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

| Schema | OneOf Group | Recommended Variant | Description |
|--------|-------------|---------------------|-------------|
| `healthcheckCreateSpecType` | `health_check` | `http_health_check` | HTTP health check type |
| `healthcheckReplaceSpecType` | `health_check` | `http_health_check` | HTTP health check type |

## Data Access

### OpenAPI Specifications

| File | Content |
|------|---------|
| `docs/specifications/api/virtual.json` | `healthcheckHttpHealthCheck`, `healthcheckCreateSpecType`, `healthcheckReplaceSpecType`, `healthcheckGetSpecType` |
| `docs/specifications/api/openapi.json` | Merged specification with all schemas |

### validation.json Structure

```text
defaults.resources.healthcheck
├── server_applied      # Fields with x-f5xc-server-default: true
├── recommended         # Fields with x-f5xc-recommended-value
├── oneof_recommended   # OneOf variant recommendations
└── nested_recommended  # Nested schema recommended values
```

## Related Documentation

- [Development Guide - OpenAPI Extensions](DEVELOPMENT.md#openapi-extensions) - Extension definitions and usage
- [Validation Specification](VALIDATION_SPEC.md) - validation.json format and structure
- [Origin Pool Enhancements](ORIGINPOOL_ENHANCEMENTS.md) - Origin pool schema enrichments

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 2.1.3 | 2026-01-18 | Consolidated global extension docs to DEVELOPMENT.md; resource-specific data only |
| 2.1.2 | 2026-01-18 | Rewritten as pure API reference; removed downstream examples |
| 2.1.1 | 2026-01-18 | Added nested recommended values, OneOf recommended variants |
| 2.1.0 | 2026-01-18 | Added unified defaults structure in validation.json |
| 2.0.30 | 2026-01-16 | Added nested defaults for `$ref` schemas |
| 2.0.29 | 2026-01-17 | Initial healthcheck defaults |

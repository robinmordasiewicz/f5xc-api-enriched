# XCSH Issue #128: Extract 7 Additional Domain Metadata Fields from f5xc-api-enriched index.json

**Status**: Ready for xcsh repository
**Issue Type**: Enhancement
**Priority**: Medium
**Epic**: xcsh code generation improvements
**Related**: f5xc-api-enriched #128, #129, #130, #131, #132, #133, #134

## Problem Statement

The xcsh code generator currently extracts only 4 fields (domain, title, description, aliases) from domain metadata in f5xc-api-enriched index.json. However, f5xc-api-enriched now provides 11 comprehensive fields per domain that would significantly enhance xcsh's domain information and CLI experience.

### Current State (xcsh DomainInfo struct)

```go
type DomainInfo struct {
    Name        string   // from domain
    DisplayName string   // from title
    Description string   // from description
    Aliases     []string // manually maintained
}
```

### Available in f5xc-api-enriched index.json (7 additional fields)

**New metadata fields (required for this issue)**:

- `complexity` (string): "simple" | "moderate" | "advanced" (NEW - calculated field)
- `is_preview` (bool): Beta/preview status
- `requires_tier` (string): "Standard" | "Professional" | "Enterprise"
- `domain_category` (string): "Infrastructure" | "Security" | "Networking" | "Operations" | "Platform" | "AI"
- `use_cases` ([]string): 3-6 business use cases
- `related_domains` ([]string): Related domain names
- `path_count` (int): Number of API endpoints
- `schema_count` (int): Number of schemas

**Optional field (if available for the domain)**:

- `cli_metadata` (object): Quick-start guides, common workflows, troubleshooting (NEW - for initial 5 domains: virtual, dns, api, site, system)

## Proposed Solution

### 1. Extend DomainInfo Struct

**File**: `cmd/generate-domains.go`

```go
type DomainInfo struct {
    // Existing fields
    Name        string
    DisplayName string
    Description string
    Aliases     []string

    // NEW: Add 8 fields from index.json
    IsPreview       bool     `json:"is_preview"`
    RequiresTier    string   `json:"requires_tier"`
    DomainCategory  string   `json:"domain_category"`
    Complexity      string   `json:"complexity"`
    UseCases        []string `json:"use_cases"`
    RelatedDomains  []string `json:"related_domains"`
    PathCount       int      `json:"path_count"`
    SchemaCount     int      `json:"schema_count"`

    // OPTIONAL: CLI metadata if available for domain
    CLIMetadata     *CLIMetadata `json:"cli_metadata,omitempty"`
}

// CLIMetadata contains domain-specific CLI guidance
type CLIMetadata struct {
    QuickStart       QuickStart        `json:"quick_start"`
    CommonWorkflows  []Workflow        `json:"common_workflows"`
    Troubleshooting  []TroubleshootStep `json:"troubleshooting"`
    Icon             string            `json:"icon"`
}

type QuickStart struct {
    Command          string `json:"command"`
    Description      string `json:"description"`
    ExpectedOutput   string `json:"expected_output"`
}

type Workflow struct {
    Name             string `json:"name"`
    Description      string `json:"description"`
    Steps            []WorkflowStep `json:"steps"`
    Prerequisites    []string `json:"prerequisites"`
    ExpectedOutcome  string `json:"expected_outcome"`
}

type WorkflowStep struct {
    Step             int    `json:"step"`
    Command          string `json:"command"`
    Description      string `json:"description"`
}

type TroubleshootStep struct {
    Problem          string   `json:"problem"`
    Symptoms         []string `json:"symptoms"`
    DiagnosisCommands []string `json:"diagnosis_commands"`
    Solutions        []string `json:"solutions"`
}
```

### 2. Fetch from index.json

**Source URL**: `https://robinmordasiewicz.github.io/f5xc-api-enriched/specifications/api/index.json`

**Index Structure** (example from virtual domain):

```json
{
  "version": "1.0.40",
  "timestamp": "2025-12-24T06:06:00.876343+00:00",
  "specifications": [
    {
      "domain": "virtual",
      "title": "F5 XC Virtual API",
      "description": "F5 Distributed Cloud Virtual API specifications",
      "file": "virtual.json",
      "path_count": 164,
      "schema_count": 1248,
      "complexity": "advanced",
      "is_preview": false,
      "requires_tier": "Professional",
      "domain_category": "Networking",
      "use_cases": [
        "Configure HTTP/TCP/UDP load balancers",
        "Manage origin pools and services",
        "Configure virtual hosts and routing"
      ],
      "related_domains": ["dns", "service_policy", "network"],
      "cli_metadata": {
        "quick_start": {
          "command": "curl $F5XC_API_URL/api/config/namespaces/default/http_loadbalancers -H 'Authorization: APIToken $F5XC_API_TOKEN'",
          "description": "List all HTTP load balancers in default namespace",
          "expected_output": "JSON array of load balancer objects with status"
        },
        "common_workflows": [
          {
            "name": "Create HTTP Load Balancer",
            "description": "Deploy basic HTTP load balancer with origin pool backend",
            "steps": [
              {
                "step": 1,
                "command": "curl -X POST $F5XC_API_URL/api/config/namespaces/default/origin_pools ...",
                "description": "Create backend origin pool with target endpoints"
              }
            ],
            "prerequisites": ["Active namespace", "Origin pool targets reachable"],
            "expected_outcome": "Load balancer in Active status, traffic routed to origins"
          }
        ],
        "troubleshooting": [
          {
            "problem": "Load balancer shows Configuration Error status",
            "symptoms": ["Status: Configuration Error", "No traffic routing"],
            "diagnosis_commands": ["curl $F5XC_API_URL/..."],
            "solutions": ["Verify origin pool targets are reachable"]
          }
        ],
        "icon": "⚖️"
      }
    }
  ]
}
```

### 3. Implementation Example

```go
package main

import (
    "encoding/json"
    "fmt"
    "io"
    "net/http"
)

func generateDomains() error {
    // Fetch index.json from GitHub Pages
    resp, err := http.Get("https://robinmordasiewicz.github.io/f5xc-api-enriched/specifications/api/index.json")
    if err != nil {
        return fmt.Errorf("fetch index.json: %w", err)
    }
    defer resp.Body.Close()

    body, err := io.ReadAll(resp.Body)
    if err != nil {
        return fmt.Errorf("read response: %w", err)
    }

    var index struct {
        Specifications []struct {
            Domain         string                 `json:"domain"`
            Title          string                 `json:"title"`
            Description    string                 `json:"description"`
            PathCount      int                    `json:"path_count"`
            SchemaCount    int                    `json:"schema_count"`
            Complexity     string                 `json:"complexity"`
            IsPreview      bool                   `json:"is_preview"`
            RequiresTier   string                 `json:"requires_tier"`
            DomainCategory string                 `json:"domain_category"`
            UseCases       []string               `json:"use_cases"`
            RelatedDomains []string               `json:"related_domains"`
            CLIMetadata    map[string]interface{} `json:"cli_metadata,omitempty"`
        } `json:"specifications"`
    }

    if err := json.Unmarshal(body, &index); err != nil {
        return fmt.Errorf("parse index.json: %w", err)
    }

    // Convert to DomainInfo
    domains := make([]DomainInfo, 0, len(index.Specifications))
    for _, entry := range index.Specifications {
        domain := DomainInfo{
            Name:           entry.Domain,
            DisplayName:    entry.Title,
            Description:    entry.Description,
            IsPreview:      entry.IsPreview,
            RequiresTier:   entry.RequiresTier,
            DomainCategory: entry.DomainCategory,
            Complexity:     entry.Complexity,
            UseCases:       entry.UseCases,
            RelatedDomains: entry.RelatedDomains,
            PathCount:      entry.PathCount,
            SchemaCount:    entry.SchemaCount,
            Aliases:        inferAliases(entry.Domain),
        }

        // Parse CLI metadata if available
        if entry.CLIMetadata != nil {
            cliMeta, err := parseCLIMetadata(entry.CLIMetadata)
            if err == nil {
                domain.CLIMetadata = cliMeta
            }
        }

        domains = append(domains, domain)
    }

    // Generate domains_generated.go
    return writeDomainFile(domains)
}

func inferAliases(domain string) []string {
    // Keep existing logic for alias inference
    aliases := []string{}
    switch domain {
    case "http_loadbalancer":
        aliases = append(aliases, "lb", "hlb")
    case "origin_pool":
        aliases = append(aliases, "pool", "backend")
    }
    return aliases
}

func parseCLIMetadata(data map[string]interface{}) (*CLIMetadata, error) {
    // Parse CLI metadata from JSON structure
    bytes, err := json.Marshal(data)
    if err != nil {
        return nil, err
    }
    var metadata CLIMetadata
    if err := json.Unmarshal(bytes, &metadata); err != nil {
        return nil, err
    }
    return &metadata, nil
}
```

## Use Cases

With these fields, xcsh can:

### 1. **Preview Warnings**

```bash
$ xcsh api create my-api
⚠️  api domain is PREVIEW - use with caution in production
```

### 2. **Tier Validation**

```bash
$ xcsh virtual create my-lb
ℹ️  virtual domain requires Professional tier (you have: Standard)
```

### 3. **Domain Organization**

```bash
$ xcsh domains list --category Networking
Virtual               ⚖️   Professional  Advanced     164 endpoints
DNS                   🌐   Standard       Moderate      24 endpoints
Service Policy        🔗   Professional  Moderate      42 endpoints
```

### 4. **Complexity Indicators**

```bash
$ xcsh site create --help
COMPLEXITY: Advanced (164 endpoints, 1248 schemas)
Create site deployment across cloud providers
```

### 5. **Related Domain Suggestions**

```json
$ xcsh virtual create my-lb
💡 Tip: Related domains - dns (manage DNS), service_policy (enforce policies)
    Try: xcsh dns create, xcsh service_policy create
```

### 6. **API Surface Statistics**

```bash
$ xcsh api info
API Security
  Endpoints: 36
  Schemas: 228
  Complexity: Moderate
  Tier Required: Professional
```

### 7. **Quick Start Command Help**

```go
$ xcsh virtual quickstart
Quick Start - Create HTTP Load Balancer:
  1. Create origin pool:
     curl -X POST $F5XC_API_URL/api/config/namespaces/default/origin_pools ...
  2. Create load balancer:
     curl -X POST $F5XC_API_URL/api/config/namespaces/default/http_loadbalancers ...
```

## Testing

### Validate index.json Accessibility

```bash
# Fetch and verify structure
curl -s https://robinmordasiewicz.github.io/f5xc-api-enriched/specifications/api/index.json | \
  jq '.specifications[0] | keys' | sort

# Expected output (minimum fields):
[
  "complexity",
  "description",
  "domain",
  "domain_category",
  "file",
  "is_preview",
  "path_count",
  "related_domains",
  "requires_tier",
  "schema_count",
  "title",
  "use_cases"
]

# With optional CLI metadata:
# "cli_metadata" may be present for select domains
```

### Verify Field Counts

```bash
# All domains should have 12 base fields + optional cli_metadata
curl -s https://robinmordasiewicz.github.io/f5xc-api-enriched/specifications/api/index.json | \
  jq '.specifications | map(keys | length) | unique'

# Expected: [12] or [12, 13] (with/without cli_metadata)
```

### Test Integration

```bash
# Build with new code
go build ./cmd/generate-domains.go

# Verify generated code includes new fields
grep -c "IsPreview\|RequiresTier\|Complexity" internal/domains/domains_generated.go

# Expected: Multiple matches (one per domain + type definition)

# Verify sample domain entries
jq '.domains[] | select(.name == "virtual") | keys' internal/domains/domains_generated.go | sort
```

## Example Generated Output

```go
// domains_generated.go
var AllDomains = []DomainInfo{
    {
        Name:           "virtual",
        DisplayName:    "F5 XC Virtual API",
        Description:    "F5 Distributed Cloud Virtual API specifications",
        Aliases:        []string{"lb", "loadbalancer"},
        IsPreview:      false,
        RequiresTier:   "Professional",
        DomainCategory: "Networking",
        Complexity:     "advanced",
        UseCases: []string{
            "Configure HTTP/TCP/UDP load balancers",
            "Manage origin pools and services",
            "Configure virtual hosts and routing",
        },
        RelatedDomains: []string{"dns", "service_policy", "network"},
        PathCount:      164,
        SchemaCount:    1248,
        CLIMetadata: &CLIMetadata{
            QuickStart: QuickStart{
                Command:        "curl $F5XC_API_URL/api/config/namespaces/default/http_loadbalancers ...",
                Description:    "List all HTTP load balancers in default namespace",
                ExpectedOutput: "JSON array of load balancer objects with status",
            },
            Icon: "⚖️",
            // ... workflows and troubleshooting
        },
    },
    {
        Name:           "dns",
        DisplayName:    "F5 XC DNS API",
        Description:    "F5 Distributed Cloud DNS API specifications",
        Aliases:        []string{"domain"},
        IsPreview:      false,
        RequiresTier:   "Standard",
        DomainCategory: "Networking",
        Complexity:     "moderate",
        UseCases: []string{
            "Configure DNS domains and records",
            "Manage DNS security policies",
            "Enable global DNS load balancing",
        },
        RelatedDomains: []string{"virtual", "http_loadbalancer"},
        PathCount:      24,
        SchemaCount:    156,
        CLIMetadata: &CLIMetadata{
            // ... quick start, workflows, troubleshooting
        },
    },
    // ... remaining 35 domains
}
```

## Implementation Checklist

- [ ] Update DomainInfo struct with 8 new fields
- [ ] Create CLIMetadata supporting types (QuickStart, Workflow, TroubleshootStep)
- [ ] Modify generate-domains.go to fetch index.json
- [ ] Parse optional CLIMetadata field
- [ ] Convert index.json entries to DomainInfo structs
- [ ] Update domains_generated.go generator
- [ ] Verify all 37 domains populated with metadata
- [ ] Add tests for metadata parsing (at least 3 domains)
- [ ] Verify domains_generated.go compiles without errors
- [ ] Update CLI help to display new fields
- [ ] Add domain category filtering to list command
- [ ] Add complexity indicator to domain info displays
- [ ] Document new fields in README

## Acceptance Criteria

- ✅ DomainInfo struct includes all 8 new fields
- ✅ generate-domains.go successfully fetches and parses index.json
- ✅ All 37 domains populated with metadata from index.json
- ✅ domains_generated.go compiles without errors
- ✅ No breaking changes to existing API
- ✅ CLI help displays domain tiers and complexity
- ✅ Unit tests pass (at least 3 domains with all fields)
- ✅ domains_generated.go properly formatted and documented
- ✅ New fields available for CLI help and domain organization features

## Backward Compatibility

- **No breaking changes**: New fields are additions only
- **Optional CLI metadata**: Only populated for 5 domains initially (virtual, dns, api, site, system)
- **Existing aliases**: Continue to work as before
- **Fallback values**: Default values for missing fields ensure robustness

## Performance Considerations

- **Network**: Single HTTP fetch of ~15-20KB index.json (minimal impact)
- **Parsing**: JSON parsing on code generation only (not at runtime)
- **Storage**: Small increase in generated code (~500 lines for new fields + metadata)

## Resources

### Source Repository

- **Main**: <https://github.com/robinmordasiewicz/f5xc-api-enriched>
- **index.json URL**: <https://robinmordasiewicz.github.io/f5xc-api-enriched/specifications/api/index.json>
- **Update Frequency**: Daily (GitHub Actions workflow)
- **Version Format**: Semantic versioning (v1.0.X)

### Related Issues in f5xc-api-enriched

- Issue #128: Domain metadata extraction (xcsh integration)
- Issue #129: Field-level description enrichment
- Issue #130: Operation danger level classification
- Issue #131: Field-level validation rules
- Issue #132: CLI metadata enrichment
- Issue #133: Operation metadata enrichment
- Issue #134: Domain complexity calculation

## Timeline

**Estimated Implementation Time**: 4-6 hours

- **Code Changes**: 2-3 hours (struct definitions, parsing logic, generation)
- **Testing**: 1-2 hours (unit tests, integration validation)
- **Documentation**: 1 hour (README, inline docs)
- **Code Review**: Buffer

## Follow-up Work

After successful integration:

1. **Expand CLI Metadata**: Add workflows for remaining 32 domains (progressive rollout)
2. **Feature Enablement**: Use new fields in CLI commands (filtering, sorting, display)
3. **Documentation Generation**: Auto-generate domain guides from metadata
4. **xcsh Website**: Display domain complexity and tier requirements in official docs

---

**Labels**: `enhancement`, `code-generation`, `metadata`, `integration`
**Epic**: xcsh domain information enhancement
**Priority**: Medium
**Type**: Feature

---

**Generated for xcsh repository integration**
*This issue provides complete implementation guidance with working code examples ready for integration into xcsh*

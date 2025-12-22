# CLI Rebranding: vesctl → xcsh

## Summary

This document describes the CLI rebranding from `vesctl` → `f5xcctl` → `xcsh` (F5 Distributed Cloud Shell).

## Rebranding History

1. **Original**: `vesctl` (Volterra CLI)
2. **Intermediate**: `f5xcctl` (F5 XC Control)
3. **Current**: `xcsh` (F5 Distributed Cloud Shell)

## Implementation Strategy

### Direct Transformation Path

We implement **direct transformation** from original `vesctl` references to `xcsh`, skipping the intermediate `f5xcctl` step:

```text
vesctl  → xcsh (direct)
f5xcctl → xcsh (removal of intermediate branding)
```

This approach is more efficient and avoids unnecessary intermediate transformations in the F5-published API specifications.

## Files Modified

### 1. Configuration Files

- **config/enrichment.yaml**: Updated branding replacements
  - Added F5XCCTL_ environment variable pattern
  - Reordered patterns for proper precedence (env vars first)
  - Direct vesctl → xcsh transformation
  - f5xcctl → xcsh removal

- **config/discovery.yaml**: Updated CLI integration
  - Changed executable from `f5xcctl` to `xcsh`
  - Updated comments to reference xcsh

### 2. Scripts

- **scripts/discover.py**: Updated CLI references
  - Help text: "Use only xcsh CLI"
  - Error messages: "xcsh CLI not available"
  - Documentation strings

- **scripts/discovery/cli_explorer.py**: Updated CLI integration
  - Default executable: `xcsh`
  - Class docstring references
  - Parameter documentation

### 3. Build System

- **Makefile**: Updated discovery targets
  - `discover-cli` target comment
  - Help text for discovery commands

### 4. Testing

- **test_branding.py**: Comprehensive test suite
  - 14 test cases covering all transformation scenarios
  - Validates vesctl → xcsh
  - Validates f5xcctl → xcsh
  - Validates environment variable transformations
  - All tests passing ✓

## Branding Transformation Rules

### CLI Tool Names

```yaml
# Case-sensitive transformations
vesctl   → xcsh
Vesctl   → Xcsh
VESCTL   → XCSH
f5xcctl  → xcsh
F5xcctl  → Xcsh
F5XCCTL  → XCSH
```

### Environment Variables

```yaml
# Pattern-based transformations (order matters!)
F5XCCTL_API_TOKEN  → XCSH_API_TOKEN
F5XCCTL_API_URL    → XCSH_API_URL
VES_API_TOKEN      → F5XC_API_TOKEN
VES_API_URL        → F5XC_API_URL
VES_<ANYTHING>     → F5XC_<ANYTHING>
```

### Protected Patterns (NOT Transformed)

These patterns are preserved to avoid breaking API functionality:

- API URLs: `https://*.volterra.io`, `https://*.volterra.us`
- Console URLs: `console.ves.volterra.io`
- API paths: `/api/config/`, `/api/data/`
- Schema references: `$ref`, `ves.io.schema.*`

## Test Results

```text
================================================================================
CLI BRANDING TRANSFORMATION TESTS
================================================================================

✓ PASS: vesctl lowercase
✓ PASS: Vesctl titlecase
✓ PASS: VESCTL uppercase
✓ PASS: f5xcctl lowercase
✓ PASS: F5xcctl titlecase
✓ PASS: F5XCCTL uppercase
✓ PASS: VES_API_TOKEN
✓ PASS: VES_API_URL
✓ PASS: Mixed CLI references
✓ PASS: F5XCCTL_API_TOKEN variable
✓ PASS: F5XCCTL_API_URL variable
✓ PASS: Documentation example
✓ PASS: Code example
✓ PASS: Environment setup

RESULTS: 14 passed, 0 failed
```

## Impact Analysis

### Backward Compatibility

- ✅ No breaking changes to API functionality
- ✅ Protected patterns preserved
- ✅ Schema references intact
- ✅ Environment variable migration path clear

### Documentation Impact

- All CLI references updated to `xcsh`
- Environment variable examples updated
- Command-line examples refreshed

### Discovered Specs

The `specs/discovered/openapi.json` file contains example data with `vesctl-test-*` namespace names. These are:

- Example/test namespaces from F5's API
- Not user-facing documentation
- Can remain as-is or be updated in future discovery runs

## Usage Examples

### Before (vesctl/f5xcctl)

```bash
# Old CLI
vesctl configuration get
f5xcctl apply -f config.yaml
export VES_API_TOKEN=xxx
export F5XCCTL_API_TOKEN=xxx
```

### After (xcsh)

```bash
# New CLI
xcsh configuration get
xcsh apply -f config.yaml
export F5XC_API_TOKEN=xxx
export XCSH_API_TOKEN=xxx
```

## Verification Steps

1. **Run Tests**: `python test_branding.py` ✓
2. **Check Config**: Verify enrichment.yaml patterns ✓
3. **Pipeline Test**: Run enrichment on sample specs ✓
4. **Discovery Test**: Verify CLI explorer configuration ✓

## Next Steps

1. ✅ Update configuration files
2. ✅ Update scripts and documentation
3. ✅ Create comprehensive test suite
4. ✅ Validate transformations
5. 🔄 Commit changes
6. 🔄 Run full pipeline test
7. 🔄 Deploy to production

## Notes

- The transformation is **idempotent** - running multiple times produces the same result
- The order of patterns in `enrichment.yaml` matters - environment variables must be processed before standalone tool names
- Protected patterns ensure API functionality is not broken
- The test suite validates all transformation scenarios

## Related Documentation

- [CLAUDE.md](CLAUDE.md): Project architecture and patterns
- [config/enrichment.yaml](config/enrichment.yaml): Full branding configuration
- [config/discovery.yaml](config/discovery.yaml): CLI integration settings

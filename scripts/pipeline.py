#!/usr/bin/env python3
"""Unified F5 XC API Enrichment Pipeline.

Single command to process all specifications from original → enriched.
Combines enrich, normalize, and merge steps into one atomic operation.
Outputs ONLY merged domain specs (no individual files).

Pipeline flow:
    specs/original/ (READ-ONLY)
        ↓
    [Enrich: branding, acronyms, grammar] (in memory)
        ↓
    [Normalize: fix $refs, clean operations] (in memory)
        ↓
    [Merge: combine by domain]
        ↓
    docs/specifications/api/
        ├── api_security.json
        ├── applications.json
        ├── bigip.json
        ├── billing.json
        ├── cdn.json
        ├── config.json
        ├── identity.json
        ├── infrastructure.json
        ├── infrastructure_protection.json
        ├── load_balancer.json
        ├── networking.json
        ├── nginx.json
        ├── observability.json
        ├── other.json
        ├── security.json
        ├── service_mesh.json
        ├── shape_security.json
        ├── subscriptions.json
        ├── tenant_management.json
        ├── vpn.json
        ├── openapi.json    (master combined spec)
        └── index.json      (spec metadata)

Usage:
    python -m scripts.pipeline              # Full pipeline
    python -m scripts.pipeline --dry-run    # Analyze without writing
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

import yaml
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

# Import processing modules
from scripts.utils import (
    AcronymNormalizer,
    BrandingTransformer,
    CLIMetadataEnricher,
    ConsistencyValidator,
    ConstraintReconciler,
    DescriptionStructureTransformer,
    DescriptionValidator,
    DiscoveryEnricher,
    FieldDescriptionEnricher,
    GrammarImprover,
    MinimumConfigurationEnricher,
    OperationMetadataEnricher,
    SchemaFixer,
    TagGenerator,
    ValidationEnricher,
    categorize_spec,
)
from scripts.utils.domain_metadata import calculate_complexity, get_metadata

console = Console()


# Default configuration
DEFAULT_CONFIG = {
    "paths": {
        "original": "specs/original",
        "enriched": "docs/specifications/api",
        "reports": "reports",
    },
    "target_fields": ["description", "summary", "title", "x-displayname"],
    "preserve_fields": ["operationId", "$ref", "x-ves-proto-rpc", "x-ves-proto-service"],
    "grammar": {
        "capitalize_sentences": True,
        "ensure_punctuation": True,
        "normalize_whitespace": True,
        "fix_double_spaces": True,
        "trim_whitespace": True,
    },
    "normalization": {
        "fix_orphan_refs": True,
        "create_missing_components": True,
        "inline_orphan_request_bodies": True,
        "remove_empty_objects": True,
        "type_standardization": True,
    },
    "processing": {
        "parallel_workers": 4,
        "continue_on_error": True,
    },
    "output": {
        "json_indent": 2,
        "sort_keys": False,
    },
}


@dataclass
class PipelineStats:
    """Statistics for the complete pipeline run."""

    files_processed: int = 0
    files_succeeded: int = 0
    files_failed: int = 0
    enrichment_changes: int = 0
    normalization_changes: int = 0
    schemas_fixed: int = 0
    operations_tagged: int = 0
    descriptions_generated: int = 0
    consistency_issues: int = 0
    minimum_configs_added: int = 0
    domains_created: int = 0
    paths_merged: int = 0
    schemas_merged: int = 0
    discovery_enriched: int = 0
    constraints_reconciled: int = 0
    constraints_preserved: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)


def load_config(config_path: Path | None = None) -> dict:
    """Load configuration from YAML file or use defaults."""
    if config_path and config_path.exists():
        with config_path.open() as f:
            config = yaml.safe_load(f) or {}
            return _deep_merge(DEFAULT_CONFIG, config)
    return DEFAULT_CONFIG


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge two dictionaries."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_spec(spec_path: Path) -> dict[str, Any]:
    """Load an OpenAPI specification from JSON file."""
    with spec_path.open() as f:
        return json.load(f)


def save_spec(spec: dict[str, Any], output_path: Path, indent: int = 2) -> None:
    """Save an OpenAPI specification to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as f:
        json.dump(spec, f, indent=indent, ensure_ascii=False)
        f.write("\n")


# =============================================================================
# ENRICHMENT FUNCTIONS
# =============================================================================


def enrich_spec(spec: dict[str, Any], config: dict) -> tuple[dict[str, Any], dict[str, int]]:
    """Apply enrichment transformations to a specification.

    Returns (enriched_spec, stats_dict) where stats_dict contains:
        - field_count: number of text fields processed
        - schemas_fixed: number of schemas fixed by SchemaFixer
        - operations_tagged: number of operations tagged
        - descriptions_generated: number of descriptions auto-generated
        - consistency_issues: number of consistency issues found
        - domains_normalized: number of domain names normalized (RFC 2606)
    """
    target_fields = config.get("target_fields", ["description", "summary", "title"])
    grammar_config = config.get("grammar", {})

    # Initialize enrichment utilities
    acronym_normalizer = AcronymNormalizer()
    branding_transformer = BrandingTransformer()
    description_structure_transformer = DescriptionStructureTransformer()
    grammar_improver = GrammarImprover(
        capitalize_sentences=grammar_config.get("capitalize_sentences", True),
        ensure_punctuation=grammar_config.get("ensure_punctuation", True),
        normalize_whitespace=grammar_config.get("normalize_whitespace", True),
        fix_double_spaces=grammar_config.get("fix_double_spaces", True),
        trim_whitespace=grammar_config.get("trim_whitespace", True),
        use_language_tool=False,  # Disable for pipeline performance
    )
    schema_fixer = SchemaFixer()
    tag_generator = TagGenerator()
    description_validator = DescriptionValidator()
    consistency_validator = ConsistencyValidator()

    # Count fields before
    field_count = _count_text_fields(spec, target_fields)

    # Apply enrichments in order:
    # 1. Branding transformations first (most specific)
    spec = branding_transformer.transform_spec(spec, target_fields)

    # 2. Description structure normalization (extract examples, validation rules)
    spec = description_structure_transformer.transform_spec(spec, target_fields)

    # 3. Acronym normalization
    spec = acronym_normalizer.normalize_spec(spec, target_fields)

    # 4. Grammar improvements
    spec = grammar_improver.improve_spec(spec, target_fields)

    # 5. Sanitize script tags in descriptions (prevent Spectral security warnings)
    spec, _script_sanitize_count = _sanitize_script_tags(spec, target_fields)

    # 6. Normalize domain names (RFC 2606 compliance + lowercase hostnames)
    spec, domain_normalize_count = _normalize_domain_names(spec, target_fields)

    # 7. Schema fixes (fix format-without-type issues)
    spec = schema_fixer.fix_spec(spec)
    schema_stats = schema_fixer.get_stats()

    # 8. Tag generation (assign tags to operations based on path patterns)
    spec = tag_generator.generate_tags(spec)
    tag_stats = tag_generator.get_stats()

    # 9. Description validation (auto-generate missing descriptions)
    spec = description_validator.validate_and_generate(spec)
    desc_stats = description_validator.get_stats()

    # 10. Consistency validation (report issues without auto-fixing)
    consistency_validator.validate(spec)
    consistency_stats = consistency_validator.get_stats()

    # 11. Field-level description enrichment (add realistic descriptions and examples)
    field_description_enricher = FieldDescriptionEnricher()
    spec = field_description_enricher.enrich_spec(spec)
    field_desc_stats = field_description_enricher.get_stats()

    # 12. Field-level validation rule enrichment (add min/max, patterns, formats)
    validation_enricher = ValidationEnricher()
    spec = validation_enricher.enrich_spec(spec)
    validation_stats = validation_enricher.get_stats()

    # 13. Field-level CLI metadata enrichment (add help text and completion hints)
    cli_metadata_enricher = CLIMetadataEnricher()
    spec = cli_metadata_enricher.enrich_spec(spec)
    cli_stats = cli_metadata_enricher.get_stats()

    # 14. Operation metadata enrichment (add danger levels, required fields, side effects, CLI examples)
    operation_metadata_enricher = OperationMetadataEnricher()
    spec = operation_metadata_enricher.enrich_spec(spec)
    op_stats = operation_metadata_enricher.get_stats()

    # 15. Minimum configuration enrichment (add x-ves-minimum-configuration extensions)
    minimum_config_enricher = MinimumConfigurationEnricher()
    spec = minimum_config_enricher.enrich_spec(spec)
    min_config_stats = minimum_config_enricher.get_stats()

    # Close grammar improver resources
    grammar_improver.close()

    return spec, {
        "field_count": field_count,
        "schemas_fixed": schema_stats.get("fixes_applied", 0),
        "operations_tagged": tag_stats.get("operations_tagged", 0),
        "descriptions_generated": desc_stats.get("operations_generated", 0)
        + desc_stats.get("schemas_generated", 0),
        "consistency_issues": consistency_stats.get("total_issues", 0),
        "domains_normalized": domain_normalize_count,
        "field_descriptions_added": field_desc_stats.get("descriptions_added", 0),
        "field_examples_added": field_desc_stats.get("examples_added", 0),
        "validation_rules_added": validation_stats.get("patterns_added", 0),
        "validation_constraints_added": validation_stats.get("constraints_added", 0),
        "cli_help_added": cli_stats.get("help_added", 0),
        "cli_completions_added": cli_stats.get("completions_added", 0),
        "operations_enriched": op_stats.get("operations_enriched", 0),
        "required_fields_added": op_stats.get("required_fields_added", 0),
        "danger_levels_assigned": op_stats.get("danger_levels_assigned", 0),
        "cli_examples_generated": op_stats.get("examples_generated", 0),
        "side_effects_documented": op_stats.get("side_effects_documented", 0),
        "minimum_configs_added": min_config_stats.get("minimum_configs_added", 0),
    }


def _count_text_fields(spec: dict[str, Any], target_fields: list[str]) -> int:
    """Count the number of text fields in a specification."""
    count = 0

    def _count_recursive(obj: Any) -> None:
        nonlocal count
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key in target_fields and isinstance(value, str):
                    count += 1
                else:
                    _count_recursive(value)
        elif isinstance(obj, list):
            for item in obj:
                _count_recursive(item)

    _count_recursive(spec)
    return count


# =============================================================================
# NORMALIZATION FUNCTIONS
# =============================================================================


def _remove_ref_siblings(spec: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Remove properties that are siblings to $ref (violates OpenAPI spec).

    OpenAPI spec requires that $ref MUST NOT have siblings.
    This function removes all properties next to $ref to comply.

    Returns (modified_spec, count_of_properties_removed).
    """
    removed_count = 0

    def clean_recursive(obj: Any) -> Any:
        nonlocal removed_count

        if isinstance(obj, dict):
            # If this dict has a $ref, remove all other properties
            if "$ref" in obj:
                removed_count += len(obj) - 1
                return {"$ref": obj["$ref"]}

            # Otherwise, recursively clean all values
            result = {}
            for key, value in obj.items():
                result[key] = clean_recursive(value)
            return result

        if isinstance(obj, list):
            return [clean_recursive(item) for item in obj]

        return obj

    cleaned_spec = clean_recursive(spec)
    return cleaned_spec, removed_count


def normalize_spec(spec: dict[str, Any], config: dict) -> tuple[dict[str, Any], int]:
    """Apply normalization to fix structural issues.

    Returns (normalized_spec, change_count).
    """
    norm_config = config.get("normalization", {})
    total_changes = 0

    # 0. Remove properties that are siblings to $ref (OpenAPI compliance)
    spec, count = _remove_ref_siblings(spec)
    total_changes += count

    # 1. Fix orphan $refs
    if norm_config.get("fix_orphan_refs", True):
        spec, count = _fix_orphan_refs(spec, norm_config)
        total_changes += count

    # 2. Inline orphan requestBodies
    if norm_config.get("inline_orphan_request_bodies", True):
        spec, count = _inline_orphan_request_bodies(spec)
        total_changes += count

    # 3. Remove empty operations
    if norm_config.get("remove_empty_objects", True):
        spec, count = _remove_empty_operations(spec)
        total_changes += count

    # 4. Normalize types
    if norm_config.get("type_standardization", True):
        spec, count = _normalize_types(spec)
        total_changes += count

    # 5. Fix invalid example schemas
    if norm_config.get("fix_invalid_examples", True):
        spec, count = _fix_invalid_examples(spec)
        total_changes += count

    return spec, total_changes


def _fix_orphan_refs(spec: dict[str, Any], _config: dict) -> tuple[dict[str, Any], int]:
    """Fix orphan $ref references by creating missing components."""
    # Collect all $refs
    all_refs: set[str] = set()

    def collect_refs(obj: Any) -> None:
        if isinstance(obj, dict):
            if "$ref" in obj and isinstance(obj["$ref"], str):
                all_refs.add(obj["$ref"])
            for value in obj.values():
                collect_refs(value)
        elif isinstance(obj, list):
            for item in obj:
                collect_refs(item)

    collect_refs(spec)

    # Get existing components
    existing: dict[str, set[str]] = defaultdict(set)
    for comp_type in ["schemas", "responses", "parameters", "requestBodies"]:
        if comp_type in spec.get("components", {}):
            existing[comp_type] = set(spec["components"][comp_type].keys())

    # Find orphans
    fixed_count = 0
    if "components" not in spec:
        spec["components"] = {}

    for ref in all_refs:
        match = re.match(r"^#/components/(\w+)/(.+)$", ref)
        if match:
            comp_type, comp_name = match.groups()
            if comp_name not in existing.get(comp_type, set()):
                # Create stub component
                if comp_type not in spec["components"]:
                    spec["components"][comp_type] = {}

                if comp_name not in spec["components"][comp_type]:
                    spec["components"][comp_type][comp_name] = _create_stub(comp_type, comp_name)
                    fixed_count += 1

    return spec, fixed_count


def _create_stub(comp_type: str, comp_name: str) -> dict[str, Any]:
    """Create a stub component definition."""

    def create_schema_stub(name: str) -> dict[str, Any]:
        return {
            "type": "object",
            "description": f"Auto-generated stub for {name}",
            "x-generated": True,
        }

    def create_request_body_stub(name: str) -> dict[str, Any]:
        return {
            "description": f"Auto-generated stub for {name}",
            "content": {"application/json": {"schema": {"type": "object"}}},
            "x-generated": True,
        }

    def create_response_stub(name: str) -> dict[str, Any]:
        return {
            "description": f"Auto-generated stub response for {name}",
            "x-generated": True,
        }

    def create_default_stub(name: str) -> dict[str, Any]:
        return {
            "description": f"Auto-generated stub for {name}",
            "x-generated": True,
        }

    stub_factories: dict[str, Callable[[str], dict[str, Any]]] = {
        "schemas": create_schema_stub,
        "requestBodies": create_request_body_stub,
        "responses": create_response_stub,
    }
    return stub_factories.get(comp_type, create_default_stub)(comp_name)


def _inline_orphan_request_bodies(spec: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Convert orphan requestBody $refs to inline definitions."""
    inlined_count = 0
    existing = set(spec.get("components", {}).get("requestBodies", {}).keys())

    for path_item in spec.get("paths", {}).values():
        if not isinstance(path_item, dict):
            continue

        for method in ["get", "post", "put", "delete", "patch"]:
            operation = path_item.get(method)
            if not isinstance(operation, dict):
                continue

            request_body = operation.get("requestBody")
            if isinstance(request_body, dict) and "$ref" in request_body:
                match = re.match(r"^#/components/requestBodies/(.+)$", request_body["$ref"])
                if match and match.group(1) not in existing:
                    operation["requestBody"] = {
                        "description": f"Request body (originally referenced {match.group(1)})",
                        "content": {"application/json": {"schema": {"type": "object"}}},
                    }
                    inlined_count += 1

    return spec, inlined_count


def _remove_empty_operations(spec: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Remove operations that have empty {} values."""
    removed_count = 0
    paths_to_remove = []

    for path, path_item in spec.get("paths", {}).items():
        if not isinstance(path_item, dict):
            continue

        methods_to_remove = []
        for method in ["get", "post", "put", "delete", "patch", "options", "head", "trace"]:
            if method in path_item:
                operation = path_item[method]
                if operation == {} or (
                    isinstance(operation, dict)
                    and not operation.get("operationId")
                    and not operation.get("responses")
                    and not operation.get("summary")
                    and not operation.get("description")
                ):
                    methods_to_remove.append(method)

        for method in methods_to_remove:
            del path_item[method]
            removed_count += 1

        remaining = [
            m
            for m in ["get", "post", "put", "delete", "patch", "options", "head", "trace"]
            if m in path_item
        ]
        if not remaining:
            paths_to_remove.append(path)

    for path in paths_to_remove:
        del spec["paths"][path]

    return spec, removed_count


def _normalize_types(spec: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Standardize type values to lowercase."""
    normalized_count = 0
    valid_types = {"string", "number", "integer", "boolean", "array", "object", "null"}

    def normalize_recursive(obj: Any) -> Any:
        nonlocal normalized_count
        if isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                if key == "type" and isinstance(value, str):
                    lower_value = value.lower()
                    if lower_value in valid_types and value != lower_value:
                        result[key] = lower_value
                        normalized_count += 1
                    else:
                        result[key] = value
                else:
                    result[key] = normalize_recursive(value)
            return result
        if isinstance(obj, list):
            return [normalize_recursive(item) for item in obj]
        return obj

    return normalize_recursive(spec), normalized_count


def _fix_invalid_examples(spec: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Fix example objects that lack required value or externalValue field.

    According to OpenAPI 3.0, Example objects in media types must have either:
    - value: Embedded example value
    - externalValue: URL pointing to external example

    This only fixes examples in media type content (e.g., requestBody/responses content),
    NOT schema properties that happen to be named "examples".

    Returns (modified_spec, fix_count).
    """
    fixed_count = 0

    def fix_examples_in_content(obj: Any, in_content: bool = False) -> Any:
        """Recursively fix examples only within content sections."""
        nonlocal fixed_count

        if isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                # Track if we're inside a content section (requestBody/responses)
                entering_content = key == "content" and isinstance(value, dict)

                # Only fix examples when inside a content section
                if key == "examples" and isinstance(value, dict) and in_content:
                    fixed_examples = {}
                    for example_name, example_value in value.items():
                        # Example object must have value or externalValue
                        if (
                            isinstance(example_value, dict)
                            and "value" not in example_value
                            and "externalValue" not in example_value
                        ):
                            fixed_example = example_value.copy()
                            fixed_example["value"] = {}
                            fixed_examples[example_name] = fixed_example
                            fixed_count += 1
                        else:
                            fixed_examples[example_name] = example_value
                    result[key] = fixed_examples
                else:
                    result[key] = fix_examples_in_content(value, in_content or entering_content)
            return result

        if isinstance(obj, list):
            return [fix_examples_in_content(item, in_content) for item in obj]

        return obj

    return fix_examples_in_content(spec), fixed_count


def _normalize_domain_names(
    spec: dict[str, Any],
    target_fields: list[str],
) -> tuple[dict[str, Any], int]:
    """Normalize domain names in documentation to RFC 2606 compliant examples.

    RFC 2606 reserves specific domains for documentation:
    - example.com, example.org, example.net
    - *.example (for any TLD)

    This function:
    1. Replaces non-compliant domains (foo.com, bar.com, etc.) with example.com
    2. Normalizes DNS hostnames to lowercase (Www.Example.com -> www.example.com)

    Args:
        spec: OpenAPI specification dictionary.
        target_fields: List of field names to process (e.g., description, summary).

    Returns:
        Tuple of (modified_spec, normalize_count).
    """
    normalize_count = 0

    # Non-RFC compliant domains to replace with example.com
    non_compliant_domains = [
        r"\bfoo\.com\b",
        r"\bbar\.com\b",
        r"\bbaz\.com\b",
        r"\btest\.com\b",
        r"\bdemo\.com\b",
        r"\bsample\.com\b",
        r"\bmysite\.com\b",
        r"\bmydomain\.com\b",
        r"\byourdomain\.com\b",
        r"\byoursite\.com\b",
        r"\bacmecorp\.com\b",
        r"\bacme\.com\b",
    ]

    # Pattern to match URLs and normalize hostname case
    # Matches http(s)://HOSTNAME or just HOSTNAME patterns
    url_pattern = re.compile(
        r"(https?://)?([A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)*\.[A-Za-z]{2,})",
        re.IGNORECASE,
    )

    def normalize_url_case(match: re.Match) -> str:
        """Normalize hostname portion of URL to lowercase."""
        protocol = match.group(1) or ""
        hostname = match.group(2)
        # Only lowercase the hostname, preserve the protocol case
        return protocol.lower() + hostname.lower()

    def normalize_text(text: str) -> tuple[str, int]:
        """Normalize domains and URL case in text."""
        changes = 0
        result = text

        # First, replace non-compliant domains with example.com
        for pattern in non_compliant_domains:
            new_result = re.sub(pattern, "example.com", result, flags=re.IGNORECASE)
            if new_result != result:
                changes += len(re.findall(pattern, result, flags=re.IGNORECASE))
                result = new_result

        # Then normalize URL/hostname case to lowercase
        # Find all URLs and check if any have uppercase
        matches = list(url_pattern.finditer(result))
        for match in reversed(matches):  # Reverse to preserve positions during replacement
            original = match.group(0)
            normalized = normalize_url_case(match)
            if original != normalized:
                result = result[: match.start()] + normalized + result[match.end() :]
                changes += 1

        return result, changes

    def normalize_recursive(obj: Any) -> Any:
        nonlocal normalize_count

        if isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                if key in target_fields and isinstance(value, str):
                    normalized, changes = normalize_text(value)
                    result[key] = normalized
                    normalize_count += changes
                else:
                    result[key] = normalize_recursive(value)
            return result

        if isinstance(obj, list):
            return [normalize_recursive(item) for item in obj]

        return obj

    return normalize_recursive(spec), normalize_count


def _sanitize_script_tags(
    spec: dict[str, Any],
    target_fields: list[str],
) -> tuple[dict[str, Any], int]:
    """Escape <script> tags from description fields.

    Spectral's no-script-tags-in-markdown rule flags descriptions containing
    <script> tags as a security warning. This function escapes them to HTML entities
    while preserving the documentation content.

    Args:
        spec: OpenAPI specification dictionary.
        target_fields: List of field names to sanitize (e.g., description, summary).

    Returns:
        Tuple of (modified_spec, sanitize_count).
    """
    sanitize_count = 0

    def sanitize_recursive(obj: Any) -> Any:
        nonlocal sanitize_count

        if isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                if key in target_fields and isinstance(value, str):
                    # Check if value contains script tags
                    if "<script" in value.lower():
                        # Escape script tags to HTML entities
                        sanitized = re.sub(
                            r"<script",
                            "&lt;script",
                            value,
                            flags=re.IGNORECASE,
                        )
                        sanitized = re.sub(
                            r"</script>",
                            "&lt;/script&gt;",
                            sanitized,
                            flags=re.IGNORECASE,
                        )
                        result[key] = sanitized
                        sanitize_count += 1
                    else:
                        result[key] = value
                else:
                    result[key] = sanitize_recursive(value)
            return result

        if isinstance(obj, list):
            return [sanitize_recursive(item) for item in obj]

        return obj

    return sanitize_recursive(spec), sanitize_count


# =============================================================================
# MERGE FUNCTIONS
# =============================================================================


def ensure_unique_operation_ids(
    paths: dict[str, Any],
    existing_ids: set[str],
    source_prefix: str,
) -> tuple[dict[str, Any], set[str], int]:
    """Ensure all operationIds in paths are unique.

    When merging specs, duplicate operationIds violate OpenAPI 3.0 requirements.
    This function prefixes duplicates with the source name to ensure uniqueness.

    Args:
        paths: Dict of path -> path_item to process.
        existing_ids: Set of operationIds already used across merged specs.
        source_prefix: Prefix to add for deduplication (derived from source filename).

    Returns:
        Tuple of (modified_paths, updated_existing_ids, dedup_count).
    """
    modified_paths = {}
    dedup_count = 0
    http_methods = {"get", "post", "put", "delete", "patch", "options", "head", "trace"}

    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            modified_paths[path] = path_item
            continue

        modified_path_item = {}
        for key, value in path_item.items():
            if key.lower() not in http_methods:
                modified_path_item[key] = value
                continue

            if not isinstance(value, dict):
                modified_path_item[key] = value
                continue

            operation = value.copy()
            op_id = operation.get("operationId", "")

            if op_id:
                if op_id in existing_ids:
                    # Generate unique operationId by prefixing with source
                    new_op_id = f"{source_prefix}_{op_id}"
                    # Handle case where prefixed ID also exists
                    counter = 1
                    while new_op_id in existing_ids:
                        new_op_id = f"{source_prefix}_{op_id}_{counter}"
                        counter += 1
                    operation["operationId"] = new_op_id
                    dedup_count += 1
                    op_id = new_op_id

                existing_ids.add(op_id)

            modified_path_item[key] = operation

        modified_paths[path] = modified_path_item

    return modified_paths, existing_ids, dedup_count


def create_base_spec(title: str, description: str, version: str) -> dict[str, Any]:
    """Create a base OpenAPI specification structure."""
    return {
        "openapi": "3.0.3",
        "info": {
            "title": title,
            "description": description,
            "version": version,
            "contact": {"name": "F5 Distributed Cloud", "url": "https://docs.cloud.f5.com"},
            "license": {"name": "Proprietary", "url": "https://www.f5.com/company/policies/eula"},
        },
        "servers": [
            {
                "url": "{api_url}/namespaces/{namespace}",
                "description": "F5 Distributed Cloud Console",
                "variables": {
                    "api_url": {
                        "default": os.getenv(
                            "F5XC_API_URL",
                            "https://example-corp.console.ves.volterra.io",
                        ),
                        "description": "F5 Distributed Cloud API URL (e.g., https://tenant.console.ves.volterra.io or https://tenant.staging.volterra.us)",
                    },
                    "namespace": {
                        "default": os.getenv("F5XC_DEFAULT_NAMESPACE", "default"),
                        "description": "Kubernetes-style namespace (e.g., 'default', 'production', 'staging', 'feature-123')",
                    },
                },
            },
        ],
        "security": [{"ApiToken": []}],
        "tags": [],
        "paths": {},
        "components": {
            "securitySchemes": {
                "ApiToken": {
                    "type": "apiKey",
                    "name": "Authorization",
                    "in": "header",
                    "description": "API Token authentication. Format: 'APIToken <your-token>'",
                },
            },
            "schemas": {},
            "responses": {},
            "parameters": {},
            "requestBodies": {},
        },
    }


def get_api_data_target_domain(path: str) -> str | None:
    """Determine the correct target domain for /api/data/ paths based on resource semantics.

    Args:
        path: API path to analyze

    Returns:
        Target domain name if path matches /api/data/ pattern, None otherwise
    """
    if "/api/data/" not in path:
        return None

    # Map resource patterns in /api/data/ paths to their semantic domains
    # Order matters: more specific patterns first
    data_routing = [
        (r"/app_security/", "waf"),
        (r"/app_firewall/", "waf"),
        (r"/dns_", "dns"),
        (r"/access_logs", "observability"),
        (r"/audit_logs", "observability"),
        (r"/alerts", "observability"),
        (r"/site/", "site"),
        (r"/virtual_k8s/", "site"),
        (r"/graph/site", "site"),
        (r"/graph/connectivity", "telemetry_and_insights"),
        (r"/graph/service", "telemetry_and_insights"),
        (r"/graph/lb_cache", "telemetry_and_insights"),
        (r"/discovered_services/", "telemetry_and_insights"),
        (r"/status_at_site", "telemetry_and_insights"),
        (r"/flow", "telemetry_and_insights"),
        (r"/infraprotect/", "ddos"),
        (r"/network_policy", "network_security"),
        (r"/service_policy", "network_security"),
        (r"/forward_proxy_policy", "network_security"),
        (r"/fast_acl/", "network_security"),
        (r"/segments/", "network_security"),
        (r"/bigip/", "bigip"),
        (r"/workloads/", "kubernetes"),
        (r"/cloud_connects", "cloud_infrastructure"),
        (r"/nfv_services/", "service_mesh"),
        (r"/virtual_network/", "service_mesh"),
        (r"/dc_cluster_groups/", "network"),
        (r"/upgrade_status", "vpm_and_node_management"),
    ]

    for pattern, target_domain in data_routing:
        if re.search(pattern, path):
            return target_domain

    # Default: if no specific match, return None (let filename-based categorization handle it)
    return None


def add_domain_metadata_to_spec(spec: dict[str, Any], domain: str) -> None:
    """Add domain classification metadata to spec (idempotent).

    Adds x-ves-cli-domain extension to the spec's info section.
    Preserves existing values if already present (idempotent behavior).

    Args:
        spec: OpenAPI specification to enhance
        domain: Domain classification (e.g., "virtual", "cdn")
    """
    if "info" not in spec:
        spec["info"] = {}

    info = spec["info"]

    # Idempotent: preserve existing x-ves-cli-domain
    if "x-ves-cli-domain" not in info:
        info["x-ves-cli-domain"] = domain


def merge_specs_by_domain(
    specs: dict[str, dict[str, Any]],
    version: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    """Merge specifications grouped by domain.

    Ensures operationId uniqueness across merged specs by prefixing
    duplicates with the source filename.

    Returns (merged_specs_by_domain, stats).
    """
    # Group specs by domain
    domain_specs: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for filename, spec in specs.items():
        domain = categorize_spec(filename)
        domain_specs[domain].append((filename, spec))

        # Also add specs to CDN domain if they contain CDN-specific paths
        paths = spec.get("paths", {})
        has_cdn_paths = any("/api/cdn/" in p or "/cdn_loadbalancers/" in p for p in paths)
        if has_cdn_paths and domain != "cdn":
            domain_specs["cdn"].append((filename, spec))

        # Also add specs to data_intelligence domain if they contain data-intelligence paths
        has_di_paths = any("/api/data-intelligence/" in p for p in paths)
        if has_di_paths and domain != "data_intelligence":
            domain_specs["data_intelligence"].append((filename, spec))

        # Also add specs to threat_campaign domain if they contain threat_campaign/threat_mesh paths
        has_threat_campaign_paths = any(
            "/api/waf/threat_campaign" in p or "/threat_mesh" in p for p in paths
        )
        if has_threat_campaign_paths and domain != "threat_campaign":
            domain_specs["threat_campaign"].append((filename, spec))

        # Also add specs to system domain if they contain credential management paths
        # Pattern-based detection for credential/token management under /api/web/
        has_credential_paths = any(
            "/api/web/" in p
            and ("/api_credentials" in p or "/service_credentials" in p or "/scim_token" in p)
            for p in paths
        )
        if has_credential_paths and domain != "authentication":
            domain_specs["authentication"].append((filename, spec))

        # Add specs to appropriate domains based on /api/data/ resource semantics
        # Collect unique target domains for /api/data/ paths in this spec
        data_path_domains = set()
        for path in paths:
            target_domain = get_api_data_target_domain(path)
            if target_domain and target_domain != domain:
                data_path_domains.add(target_domain)

        # Add this spec to all relevant /api/data/ target domains
        for target_domain in data_path_domains:
            domain_specs[target_domain].append((filename, spec))

    merged = {}
    stats = {
        "domains": 0,
        "paths": 0,
        "schemas": 0,
        "requestBodies": 0,
        "operationIds_deduplicated": 0,
    }

    for domain, spec_list in sorted(domain_specs.items()):
        domain_title = domain.replace("_", " ").title()
        merged_spec = create_base_spec(
            title=f"F5 XC {domain_title} API",
            description=f"F5 Distributed Cloud {domain_title} API specifications",
            version=version,
        )

        all_tags = []
        existing_operation_ids: set[str] = set()  # Track operationIds within domain

        for filename, spec in spec_list:
            # Extract source name for prefix (remove .json and common patterns)
            source_prefix = re.sub(r"\.json$", "", filename)
            source_prefix = re.sub(r"^ves\.io\.schema\.", "", source_prefix)
            source_prefix = re.sub(r"[^a-zA-Z0-9_]", "_", source_prefix)

            # Process paths with operationId deduplication
            spec_paths = spec.get("paths", {})
            deduplicated_paths, existing_operation_ids, dedup_count = ensure_unique_operation_ids(
                spec_paths,
                existing_operation_ids,
                source_prefix,
            )
            stats["operationIds_deduplicated"] += dedup_count

            # Merge deduplicated paths
            # Skip domain-specific paths when not merging into their target domains
            is_cdn_domain = domain == "cdn"
            is_data_intelligence_domain = domain == "data_intelligence"
            is_virtual_domain = domain == "virtual"
            is_auth_domain = domain == "authentication"
            is_threat_campaign_domain = domain == "threat_campaign"

            for path, path_item in deduplicated_paths.items():
                # Skip CDN paths if not merging into CDN domain
                if not is_cdn_domain and ("/api/cdn/" in path or "/cdn_loadbalancers/" in path):
                    continue

                # Skip threat_campaign/threat_mesh paths if not merging into threat_campaign domain
                if not is_threat_campaign_domain and (
                    "/api/waf/threat_campaign" in path or "/threat_mesh" in path
                ):
                    continue

                # Skip data-intelligence paths if not merging into data_intelligence domain
                if not is_data_intelligence_domain and "/api/data-intelligence/" in path:
                    continue

                # Skip http_loadbalancers paths if not merging into virtual domain
                if not is_virtual_domain and "/http_loadbalancers" in path:
                    continue

                # Skip credential management paths if not merging into authentication domain
                # Pattern-based: /api/web/ + (api_credentials|service_credentials|scim_token)
                is_credential_path = "/api/web/" in path and (
                    "/api_credentials" in path
                    or "/service_credentials" in path
                    or "/scim_token" in path
                )
                if not is_auth_domain and is_credential_path:
                    continue

                # Skip /api/data/ paths if not merging into their semantic target domain
                # This prevents app_security data paths from appearing in CDN domain
                data_target_domain = get_api_data_target_domain(path)
                if data_target_domain and data_target_domain != domain:
                    continue

                if path not in merged_spec["paths"]:
                    merged_spec["paths"][path] = path_item
                    stats["paths"] += 1
                else:
                    for method, operation in path_item.items():
                        if method not in merged_spec["paths"][path]:
                            merged_spec["paths"][path][method] = operation
                            stats["paths"] += 1

            # Merge components
            for comp_type in ["schemas", "responses", "parameters", "requestBodies"]:
                source_comps = spec.get("components", {}).get(comp_type, {})
                target_comps = merged_spec["components"].setdefault(comp_type, {})
                for name, comp in source_comps.items():
                    if name not in target_comps:
                        target_comps[name] = comp
                        if comp_type == "schemas":
                            stats["schemas"] += 1
                        elif comp_type == "requestBodies":
                            stats["requestBodies"] += 1

            # Collect tags
            all_tags.extend(spec.get("tags", []))
            for path_item in spec.get("paths", {}).values():
                for operation in path_item.values():
                    if isinstance(operation, dict):
                        all_tags.extend({"name": tag} for tag in operation.get("tags", []))

        # Deduplicate tags
        seen = set()
        unique_tags = []
        for tag in all_tags:
            name = tag.get("name") if isinstance(tag, dict) else tag
            if name and name not in seen:
                unique_tags.append(tag if isinstance(tag, dict) else {"name": tag})
                seen.add(name)
        merged_spec["tags"] = sorted(unique_tags, key=lambda t: t.get("name", ""))

        # Add spec-level domain metadata (idempotent)
        add_domain_metadata_to_spec(merged_spec, domain)

        merged[domain] = merged_spec
        stats["domains"] += 1

    return merged, stats


def create_master_spec(domain_specs: dict[str, dict[str, Any]], version: str) -> dict[str, Any]:
    """Create a master specification combining all domains.

    Ensures operationId uniqueness across all domains by prefixing
    cross-domain duplicates with the domain name.
    """
    master = create_base_spec(
        title="F5 Distributed Cloud API",
        description="Complete F5 Distributed Cloud API specification",
        version=version,
    )

    all_tags = []
    existing_operation_ids: set[str] = set()  # Track operationIds across all domains

    for domain, spec in domain_specs.items():
        # Process paths with operationId deduplication across domains
        spec_paths = spec.get("paths", {})
        deduplicated_paths, existing_operation_ids, _ = ensure_unique_operation_ids(
            spec_paths,
            existing_operation_ids,
            domain,  # Use domain name as prefix for cross-domain deduplication
        )

        # Merge deduplicated paths
        for path, path_item in deduplicated_paths.items():
            if path not in master["paths"]:
                master["paths"][path] = path_item

        # Merge components
        for comp_type in ["schemas", "responses", "parameters", "requestBodies"]:
            source_comps = spec.get("components", {}).get(comp_type, {})
            target_comps = master["components"].setdefault(comp_type, {})
            for name, comp in source_comps.items():
                if name not in target_comps:
                    target_comps[name] = comp

        all_tags.extend(spec.get("tags", []))

    # Deduplicate tags
    seen: set[str] = set()
    unique_tags = []
    for tag in all_tags:
        name = tag.get("name") if isinstance(tag, dict) else tag
        if name and name not in seen:
            unique_tags.append(tag if isinstance(tag, dict) else {"name": tag})
            seen.add(name)

    def get_tag_name(t: dict[str, Any]) -> str:
        return t.get("name", "")

    master["tags"] = sorted(unique_tags, key=get_tag_name)

    return master


def create_spec_index(domain_specs: dict[str, dict[str, Any]], version: str) -> dict[str, Any]:
    """Create an index file listing all available specifications."""
    index: dict[str, Any] = {
        "version": version,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "specifications": [],
    }

    for domain, spec in sorted(domain_specs.items()):
        info = spec.get("info", {})
        metadata = get_metadata(domain)

        # Calculate path and schema counts
        path_count = len(spec.get("paths", {}))
        schema_count = len(spec.get("components", {}).get("schemas", {}))
        complexity = calculate_complexity(path_count, schema_count)

        # Build spec entry
        spec_entry = {
            "domain": domain,
            "title": info.get("title", ""),
            "description": info.get("description", ""),
            "file": f"{domain}.json",
            "path_count": path_count,
            "schema_count": schema_count,
            "complexity": complexity,
            "is_preview": metadata.get("is_preview", False),
            "requires_tier": metadata.get("requires_tier", "Standard"),
            "domain_category": metadata.get("domain_category", "Other"),
            "use_cases": metadata.get("use_cases", []),
            "related_domains": metadata.get("related_domains", []),
        }

        # Add CLI metadata if available
        cli_metadata = metadata.get("cli_metadata")
        if cli_metadata:
            spec_entry["cli_metadata"] = cli_metadata

        index["specifications"].append(spec_entry)

    return index


# =============================================================================
# MAIN PIPELINE
# =============================================================================


def get_version() -> str:
    """Get version from .version file or generate date-based version."""
    version_file = Path(".version")
    if version_file.exists():
        return version_file.read_text().strip()
    return datetime.now(tz=timezone.utc).strftime("%Y.%m.%d")


def run_pipeline(
    input_dir: Path,
    output_dir: Path,
    config: dict,
    dry_run: bool = False,
) -> PipelineStats:
    """Run the complete enrichment pipeline.

    Processes specs in memory (enrich → normalize → discovery → reconcile) then merges by domain.
    No individual files are written - only merged domain specs.

    Args:
        input_dir: Directory containing original specifications (READ-ONLY).
        output_dir: Directory for merged domain specs output.
        config: Pipeline configuration.
        dry_run: Analyze without writing output.

    Returns:
        PipelineStats with processing summary.
    """
    stats = PipelineStats()

    # Find all spec files
    spec_files = sorted(input_dir.glob("*.json"))
    if not spec_files:
        console.print(f"[yellow]No specification files found in {input_dir}[/yellow]")
        return stats

    console.print(f"[blue]Found {len(spec_files)} specification files[/blue]")

    # Create output directory and clean old files
    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

        # Remove all existing JSON spec files to ensure clean state
        # This prevents rogue/stale files from previous runs
        for json_file in output_dir.glob("*.json"):
            json_file.unlink()
            console.print(f"[dim]Cleaned: {json_file.name}[/dim]")

    # Load discovery enrichment configuration
    discovery_config_path = Path("config/discovery_enrichment.yaml")
    discovery_config: dict = {}
    if discovery_config_path.exists():
        with discovery_config_path.open() as f:
            discovery_config = yaml.safe_load(f) or {}

    # Check if discovery enrichment is enabled
    discovery_enabled = config.get("discovery_enrichment", {}).get("enabled", False)
    discovery_enricher = None
    discovery_data = None

    if discovery_enabled:
        discovery_settings = discovery_config.get("discovery_enrichment", {})
        discovered_dir = Path(discovery_settings.get("discovered_specs_dir", "specs/discovered"))

        if discovered_dir.exists() and (discovered_dir / "openapi.json").exists():
            console.print("[blue]Loading discovery data for enrichment...[/blue]")
            discovery_enricher = DiscoveryEnricher(discovery_settings)
            discovery_data = discovery_enricher.load_discovery_data(discovered_dir)
            console.print(
                f"[green]Discovery data loaded: {len(discovery_data.schemas)} schemas, "
                f"{len(discovery_data.paths)} paths[/green]",
            )
        else:
            console.print(
                "[yellow]Discovery enrichment enabled but no discovery data found[/yellow]",
            )

    # Check if constraint reconciliation is enabled
    reconciliation_config = discovery_config.get("reconciliation", {})
    reconciliation_enabled = reconciliation_config.get("enabled", True) and discovery_enabled
    reconciler = None

    if reconciliation_enabled:
        reconciler = ConstraintReconciler(reconciliation_config)
        console.print(
            f"[blue]Constraint reconciliation enabled (mode: {reconciler.mode})[/blue]",
        )

    # Process specs in memory
    processed_specs: dict[str, dict[str, Any]] = {}
    output_config = config.get("output", {})
    indent = output_config.get("json_indent", 2)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Processing specifications...", total=len(spec_files))

        for spec_file in spec_files:
            try:
                # Load original spec
                spec = load_spec(spec_file)

                # Step 1: Enrich (in memory)
                spec, enrich_stats = enrich_spec(spec, config)
                stats.enrichment_changes += enrich_stats.get("field_count", 0)
                stats.schemas_fixed += enrich_stats.get("schemas_fixed", 0)
                stats.operations_tagged += enrich_stats.get("operations_tagged", 0)
                stats.descriptions_generated += enrich_stats.get("descriptions_generated", 0)
                stats.consistency_issues += enrich_stats.get("consistency_issues", 0)
                stats.minimum_configs_added += enrich_stats.get("minimum_configs_added", 0)

                # Step 2: Normalize (in memory)
                spec, norm_count = normalize_spec(spec, config)
                stats.normalization_changes += norm_count

                # Step 3: Discovery enrichment (in memory)
                if discovery_enricher and discovery_data:
                    spec = discovery_enricher.enrich_with_discoveries(spec, discovery_data)
                    discovery_stats = discovery_enricher.get_stats()
                    stats.discovery_enriched += discovery_stats.get("fields_enriched", 0)

                # Step 4: Constraint reconciliation (in memory)
                if reconciler:
                    spec, reconcile_report = reconciler.reconcile_spec(spec)
                    reconcile_stats = reconcile_report.get("statistics", {})
                    stats.constraints_reconciled += reconcile_stats.get("reconciled", 0)
                    stats.constraints_preserved += reconcile_stats.get("preserved", 0)

                # Store for merging (no individual file output)
                processed_specs[spec_file.name] = spec
                stats.files_succeeded += 1

            except Exception as e:
                stats.files_failed += 1
                stats.errors.append({"file": spec_file.name, "error": str(e)})
                if not config.get("processing", {}).get("continue_on_error", True):
                    raise

            stats.files_processed += 1
            progress.update(task, advance=1)

    # Step 5: Merge by domain (only merged specs are written)
    if not dry_run and processed_specs:
        console.print("[blue]Merging specifications by domain...[/blue]")
        version = get_version()

        domain_specs, merge_stats = merge_specs_by_domain(processed_specs, version)
        stats.domains_created = merge_stats["domains"]
        stats.paths_merged = merge_stats["paths"]
        stats.schemas_merged = merge_stats["schemas"]

        # Save domain specs
        for domain, spec in domain_specs.items():
            save_spec(spec, output_dir / f"{domain}.json", indent=indent)

        # Create master spec
        master = create_master_spec(domain_specs, version)
        save_spec(master, output_dir / "openapi.json", indent=indent)

        # Create index
        index = create_spec_index(domain_specs, version)
        save_spec(index, output_dir / "index.json", indent=indent)

        console.print(f"[green]Created {len(domain_specs)} domain specs + master spec[/green]")

    return stats


def print_summary(stats: PipelineStats) -> None:
    """Print pipeline summary to console."""
    table = Table(title="Pipeline Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Files Processed", str(stats.files_processed))
    table.add_row("Files Succeeded", str(stats.files_succeeded))
    table.add_row("Files Failed", str(stats.files_failed))
    table.add_row("Enrichment Changes", str(stats.enrichment_changes))
    table.add_row("Normalization Changes", str(stats.normalization_changes))
    table.add_row("Schemas Fixed", str(stats.schemas_fixed))
    table.add_row("Operations Tagged", str(stats.operations_tagged))
    table.add_row("Descriptions Generated", str(stats.descriptions_generated))
    table.add_row("Consistency Issues", str(stats.consistency_issues))
    table.add_row("Minimum Configs Added", str(stats.minimum_configs_added))
    table.add_row("Domains Created", str(stats.domains_created))
    table.add_row("Paths Merged", str(stats.paths_merged))
    table.add_row("Schemas Merged", str(stats.schemas_merged))

    # Discovery enrichment stats (if any)
    if stats.discovery_enriched > 0:
        table.add_row("Discovery Enriched", str(stats.discovery_enriched))
    if stats.constraints_reconciled > 0:
        table.add_row("Constraints Reconciled", str(stats.constraints_reconciled))
    if stats.constraints_preserved > 0:
        table.add_row("Custom Extensions Preserved", str(stats.constraints_preserved))

    console.print(table)

    if stats.errors:
        console.print(f"\n[red]Errors ({len(stats.errors)}):[/red]")
        for error in stats.errors[:10]:
            console.print(f"  - {error['file']}: {error['error'][:100]}...")
        if len(stats.errors) > 10:
            console.print(f"  ... and {len(stats.errors) - 10} more errors")


def generate_report(stats: PipelineStats, output_path: Path) -> None:
    """Generate pipeline report."""
    report = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "summary": {
            "files_processed": stats.files_processed,
            "files_succeeded": stats.files_succeeded,
            "files_failed": stats.files_failed,
            "enrichment_changes": stats.enrichment_changes,
            "normalization_changes": stats.normalization_changes,
            "schemas_fixed": stats.schemas_fixed,
            "operations_tagged": stats.operations_tagged,
            "descriptions_generated": stats.descriptions_generated,
            "consistency_issues": stats.consistency_issues,
            "minimum_configs_added": stats.minimum_configs_added,
            "domains_created": stats.domains_created,
            "paths_merged": stats.paths_merged,
            "schemas_merged": stats.schemas_merged,
            "discovery_enriched": stats.discovery_enriched,
            "constraints_reconciled": stats.constraints_reconciled,
            "constraints_preserved": stats.constraints_preserved,
        },
        "errors": stats.errors,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as f:
        json.dump(report, f, indent=2)
        f.write("\n")

    console.print(f"[green]Report saved to {output_path}[/green]")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="F5 XC API Enrichment Pipeline - unified processing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m scripts.pipeline              # Full pipeline
    python -m scripts.pipeline --dry-run    # Analyze without writing

Output (merged domain specs only):
    docs/specifications/api/
        ├── api_security.json
        ├── applications.json
        ├── bigip.json
        ├── billing.json
        ├── cdn.json
        ├── config.json
        ├── identity.json
        ├── infrastructure.json
        ├── infrastructure_protection.json
        ├── load_balancer.json
        ├── networking.json
        ├── nginx.json
        ├── observability.json
        ├── other.json
        ├── security.json
        ├── service_mesh.json
        ├── shape_security.json
        ├── subscriptions.json
        ├── tenant_management.json
        ├── vpn.json
        ├── openapi.json    (master combined spec)
        └── index.json      (spec metadata)
        """,
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/enrichment.yaml"),
        help="Path to configuration file",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        help="Override input directory for original specs",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Override output directory for enriched specs",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyze specs without writing output",
    )

    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config)

    # Auto-enable discovery enrichment if environment variable is set
    # This allows GitHub Actions to enable discovery without config changes
    if os.environ.get("DISCOVERY_ENRICHMENT_ENABLED", "").lower() == "true":
        if "discovery_enrichment" not in config:
            config["discovery_enrichment"] = {}
        config["discovery_enrichment"]["enabled"] = True
        console.print(
            "[blue]Discovery enrichment enabled via DISCOVERY_ENRICHMENT_ENABLED env var[/blue]",
        )

    # Determine directories
    input_dir = args.input_dir or Path(config["paths"]["original"])
    output_dir = args.output_dir or Path(config["paths"]["enriched"])
    report_dir = Path(config["paths"]["reports"])

    console.print("[bold blue]F5 XC API Enrichment Pipeline[/bold blue]")
    console.print(f"  Input:  {input_dir}")
    console.print(f"  Output: {output_dir}")

    if args.dry_run:
        console.print("  [yellow]Mode: DRY RUN (no files will be written)[/yellow]")

    if not input_dir.exists():
        console.print(f"[red]Input directory not found: {input_dir}[/red]")
        console.print("[yellow]Run 'make download' or 'python -m scripts.download' first[/yellow]")
        return 1

    # Run pipeline
    stats = run_pipeline(
        input_dir=input_dir,
        output_dir=output_dir,
        config=config,
        dry_run=args.dry_run,
    )

    # Generate report
    if not args.dry_run:
        report_path = report_dir / "pipeline-report.json"
        generate_report(stats, report_path)

    # Print summary
    print_summary(stats)

    # Exit with error if any files failed
    if stats.files_failed > 0:
        console.print(f"\n[yellow]Completed with {stats.files_failed} failures[/yellow]")
        return 1 if not config.get("processing", {}).get("continue_on_error", True) else 0

    console.print(f"\n[bold green]Pipeline complete! Output: {output_dir}[/bold green]")
    return 0


if __name__ == "__main__":
    sys.exit(main())

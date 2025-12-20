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
from scripts.merge_specs import DOMAIN_PATTERNS
from scripts.utils import (
    AcronymNormalizer,
    BrandingTransformer,
    ConsistencyValidator,
    DescriptionStructureTransformer,
    DescriptionValidator,
    GrammarImprover,
    SchemaFixer,
    TagGenerator,
)

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
    domains_created: int = 0
    paths_merged: int = 0
    schemas_merged: int = 0
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

    # 5. Schema fixes (fix format-without-type issues)
    spec = schema_fixer.fix_spec(spec)
    schema_stats = schema_fixer.get_stats()

    # 6. Tag generation (assign tags to operations based on path patterns)
    spec = tag_generator.generate_tags(spec)
    tag_stats = tag_generator.get_stats()

    # 7. Description validation (auto-generate missing descriptions)
    spec = description_validator.validate_and_generate(spec)
    desc_stats = description_validator.get_stats()

    # 8. Consistency validation (report issues without auto-fixing)
    consistency_validator.validate(spec)
    consistency_stats = consistency_validator.get_stats()

    # Close grammar improver resources
    grammar_improver.close()

    return spec, {
        "field_count": field_count,
        "schemas_fixed": schema_stats.get("fixes_applied", 0),
        "operations_tagged": tag_stats.get("operations_tagged", 0),
        "descriptions_generated": desc_stats.get("operations_generated", 0)
        + desc_stats.get("schemas_generated", 0),
        "consistency_issues": consistency_stats.get("total_issues", 0),
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


def normalize_spec(spec: dict[str, Any], config: dict) -> tuple[dict[str, Any], int]:
    """Apply normalization to fix structural issues.

    Returns (normalized_spec, change_count).
    """
    norm_config = config.get("normalization", {})
    total_changes = 0

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


# =============================================================================
# MERGE FUNCTIONS
# =============================================================================


def categorize_spec(filename: str) -> str:
    """Categorize a specification file by domain based on filename patterns."""
    filename_lower = filename.lower()
    for domain, patterns in DOMAIN_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, filename_lower):
                return domain
    return "other"


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
                "url": "https://{tenant}.console.ves.volterra.io",
                "description": "F5 Distributed Cloud Console",
                "variables": {
                    "tenant": {"default": "console", "description": "Your F5 XC tenant name"},
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


def merge_specs_by_domain(
    specs: dict[str, dict[str, Any]],
    version: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    """Merge specifications grouped by domain.

    Returns (merged_specs_by_domain, stats).
    """
    # Group specs by domain
    domain_specs: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for filename, spec in specs.items():
        domain = categorize_spec(filename)
        domain_specs[domain].append((filename, spec))

    merged = {}
    stats = {"domains": 0, "paths": 0, "schemas": 0, "requestBodies": 0}

    for domain, spec_list in sorted(domain_specs.items()):
        domain_title = domain.replace("_", " ").title()
        merged_spec = create_base_spec(
            title=f"F5 XC {domain_title} API",
            description=f"F5 Distributed Cloud {domain_title} API specifications",
            version=version,
        )

        all_tags = []
        for _filename, spec in spec_list:
            # Merge paths
            for path, path_item in spec.get("paths", {}).items():
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

        merged[domain] = merged_spec
        stats["domains"] += 1

    return merged, stats


def create_master_spec(domain_specs: dict[str, dict[str, Any]], version: str) -> dict[str, Any]:
    """Create a master specification combining all domains."""
    master = create_base_spec(
        title="F5 Distributed Cloud API",
        description="Complete F5 Distributed Cloud API specification",
        version=version,
    )

    all_tags = []
    for spec in domain_specs.values():
        # Merge paths
        for path, path_item in spec.get("paths", {}).items():
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
        index["specifications"].append(
            {
                "domain": domain,
                "title": info.get("title", ""),
                "description": info.get("description", ""),
                "file": f"{domain}.json",
                "path_count": len(spec.get("paths", {})),
                "schema_count": len(spec.get("components", {}).get("schemas", {})),
            },
        )

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

    Processes specs in memory (enrich → normalize) then merges by domain.
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

    # Create output directory
    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

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

                # Step 2: Normalize (in memory)
                spec, norm_count = normalize_spec(spec, config)
                stats.normalization_changes += norm_count

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

    # Step 3: Merge by domain (only merged specs are written)
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
    table.add_row("Domains Created", str(stats.domains_created))
    table.add_row("Paths Merged", str(stats.paths_merged))
    table.add_row("Schemas Merged", str(stats.schemas_merged))

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
            "domains_created": stats.domains_created,
            "paths_merged": stats.paths_merged,
            "schemas_merged": stats.schemas_merged,
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

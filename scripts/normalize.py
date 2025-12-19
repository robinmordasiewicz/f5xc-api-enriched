#!/usr/bin/env python3
"""Normalize OpenAPI specifications to fix structural issues.

Resolves orphan $ref references, removes empty operations, and ensures
schema compliance for Scalar and Swagger UI compatibility.
Fully automated - no manual intervention required.

IMPORTANT: This script reads from docs/specifications/api and writes in-place.
The original specs (specs/original/) are NEVER modified.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
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

console = Console()


# Default configuration
DEFAULT_CONFIG = {
    "paths": {
        "enriched": "docs/specifications/api",
        "normalized": "docs/specifications/api",
        "reports": "reports",
    },
    "normalization": {
        "fix_orphan_refs": True,
        "create_missing_components": True,
        "inline_orphan_request_bodies": True,
        "remove_empty_objects": True,
        "detect_circular_refs": True,
        "type_standardization": True,
        "remove_orphan_operations": True,
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
class NormalizationStats:
    """Statistics for normalization processing."""

    files_processed: int = 0
    files_succeeded: int = 0
    files_failed: int = 0
    orphan_refs_fixed: int = 0
    empty_operations_removed: int = 0
    missing_components_created: int = 0
    circular_refs_broken: int = 0
    types_normalized: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class NormalizationResult:
    """Result of normalizing a single specification file."""

    filename: str
    success: bool
    changes: dict[str, int] = field(default_factory=dict)
    error: str | None = None


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


def save_spec(
    spec: dict[str, Any],
    output_path: Path,
    indent: int = 2,
    sort_keys: bool = False,
) -> None:
    """Save an OpenAPI specification to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as f:
        json.dump(spec, f, indent=indent, sort_keys=sort_keys, ensure_ascii=False)
        f.write("\n")


def collect_all_refs(obj: Any, refs: set[str] | None = None, path: str = "") -> set[str]:
    """Collect all $ref values in a specification."""
    if refs is None:
        refs = set()

    if isinstance(obj, dict):
        if "$ref" in obj and isinstance(obj["$ref"], str):
            refs.add(obj["$ref"])
        for key, value in obj.items():
            collect_all_refs(value, refs, f"{path}/{key}")
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            collect_all_refs(item, refs, f"{path}[{i}]")

    return refs


def get_component_from_ref(ref: str) -> tuple[str, str] | None:
    """Extract component type and name from a $ref string.

    Returns (component_type, component_name) or None if not a local component ref.
    """
    # Match patterns like #/components/schemas/MySchema
    match = re.match(r"^#/components/(\w+)/(.+)$", ref)
    if match:
        return match.group(1), match.group(2)
    return None


def get_existing_components(spec: dict[str, Any]) -> dict[str, set[str]]:
    """Get all existing components organized by type."""
    components = defaultdict(set)
    spec_components = spec.get("components", {})

    for component_type in [
        "schemas",
        "responses",
        "parameters",
        "examples",
        "requestBodies",
        "headers",
        "securitySchemes",
        "links",
        "callbacks",
    ]:
        if component_type in spec_components:
            components[component_type] = set(spec_components[component_type].keys())

    return components


def find_orphan_refs(spec: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Find all $refs that point to non-existent components.

    Returns list of (ref_string, component_type, component_name).
    """
    all_refs = collect_all_refs(spec)
    existing_components = get_existing_components(spec)
    orphans = []

    for ref in all_refs:
        parsed = get_component_from_ref(ref)
        if parsed:
            component_type, component_name = parsed
            if component_name not in existing_components.get(component_type, set()):
                orphans.append((ref, component_type, component_name))

    return orphans


def create_stub_component(component_type: str, component_name: str) -> dict[str, Any]:
    """Create a stub component definition."""

    def _schema_stub(name: str) -> dict[str, Any]:
        return {
            "type": "object",
            "description": f"Auto-generated stub for {name}",
            "x-generated": True,
        }

    def _request_body_stub(name: str) -> dict[str, Any]:
        return {
            "description": f"Auto-generated stub for {name}",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "description": f"Request body for {name}",
                    },
                },
            },
            "x-generated": True,
        }

    def _response_stub(name: str) -> dict[str, Any]:
        return {
            "description": f"Auto-generated stub response for {name}",
            "x-generated": True,
        }

    def _parameter_stub(name: str) -> dict[str, Any]:
        return {
            "name": name,
            "in": "query",
            "description": f"Auto-generated stub parameter for {name}",
            "schema": {"type": "string"},
            "x-generated": True,
        }

    def _default_stub(name: str) -> dict[str, Any]:
        return {
            "description": f"Auto-generated stub for {name}",
            "x-generated": True,
        }

    stub_factories: dict[str, Callable[[str], dict[str, Any]]] = {
        "schemas": _schema_stub,
        "requestBodies": _request_body_stub,
        "responses": _response_stub,
        "parameters": _parameter_stub,
    }
    return stub_factories.get(component_type, _default_stub)(component_name)


def fix_orphan_refs(spec: dict[str, Any], config: dict) -> tuple[dict[str, Any], int]:
    """Fix orphan $ref references by creating missing components.

    Returns (modified_spec, count_of_fixes).
    """
    norm_config = config.get("normalization", {})
    create_missing = norm_config.get("create_missing_components", True)

    orphans = find_orphan_refs(spec)
    if not orphans:
        return spec, 0

    fixed_count = 0

    # Ensure components section exists
    if "components" not in spec:
        spec["components"] = {}

    for _ref, component_type, component_name in orphans:
        if create_missing:
            # Create the missing component
            if component_type not in spec["components"]:
                spec["components"][component_type] = {}

            if component_name not in spec["components"][component_type]:
                spec["components"][component_type][component_name] = create_stub_component(
                    component_type,
                    component_name,
                )
                fixed_count += 1

    return spec, fixed_count


def remove_empty_operations(spec: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Remove operations that have empty {} values which break Scalar.

    Returns (modified_spec, count_of_removals).
    """
    removed_count = 0
    paths = spec.get("paths", {})
    paths_to_remove = []

    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue

        methods_to_remove = []
        for method in ["get", "post", "put", "delete", "patch", "options", "head", "trace"]:
            if method in path_item:
                operation = path_item[method]
                # Check if operation is empty or has empty critical fields
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

        # Mark path for removal if no methods left
        remaining_methods = [
            m
            for m in ["get", "post", "put", "delete", "patch", "options", "head", "trace"]
            if m in path_item
        ]
        if not remaining_methods:
            paths_to_remove.append(path)

    # Remove empty paths
    for path in paths_to_remove:
        del paths[path]

    return spec, removed_count


def inline_orphan_request_bodies(spec: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Convert orphan requestBody $refs to inline definitions.

    Returns (modified_spec, count_of_inlines).
    """
    inlined_count = 0
    paths = spec.get("paths", {})
    existing_request_bodies = spec.get("components", {}).get("requestBodies", {})

    for path_item in paths.values():
        if not isinstance(path_item, dict):
            continue

        for method in ["get", "post", "put", "delete", "patch"]:
            if method not in path_item:
                continue

            operation = path_item[method]
            if not isinstance(operation, dict):
                continue

            request_body = operation.get("requestBody")
            if isinstance(request_body, dict) and "$ref" in request_body:
                ref = request_body["$ref"]
                parsed = get_component_from_ref(ref)

                if parsed and parsed[0] == "requestBodies":
                    component_name = parsed[1]
                    if component_name not in existing_request_bodies:
                        # Inline a generic request body
                        operation["requestBody"] = {
                            "description": f"Request body (originally referenced {component_name})",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                    },
                                },
                            },
                        }
                        inlined_count += 1

    return spec, inlined_count


def normalize_types(spec: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Standardize type values to lowercase.

    Returns (modified_spec, count_of_normalizations).
    """
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


def detect_and_break_circular_refs(spec: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Detect and break circular $ref chains.

    Note: This is a simplified implementation that marks potential circular refs.
    Full circular reference resolution is complex and may require deeper analysis.

    Returns (modified_spec, count_of_breaks).
    """
    # For now, just track that we checked - full implementation would be more complex
    # This is a placeholder for future enhancement
    return spec, 0


def normalize_spec_file(
    spec_path: Path,
    output_path: Path,
    config: dict,
) -> NormalizationResult:
    """Normalize a single specification file.

    Args:
        spec_path: Path to the enriched specification file.
        output_path: Path to save the normalized specification.
        config: Normalization configuration.

    Returns:
        NormalizationResult with processing details.
    """
    filename = spec_path.name
    changes = defaultdict(int)

    try:
        # Load specification
        spec = load_spec(spec_path)
        norm_config = config.get("normalization", {})

        # Apply normalizations in order

        # 1. Fix orphan $refs by creating missing components
        if norm_config.get("fix_orphan_refs", True):
            spec, count = fix_orphan_refs(spec, config)
            changes["orphan_refs_fixed"] = count

        # 2. Inline orphan requestBodies
        if norm_config.get("inline_orphan_request_bodies", True):
            spec, count = inline_orphan_request_bodies(spec)
            changes["request_bodies_inlined"] = count

        # 3. Remove empty operations
        if norm_config.get("remove_empty_objects", True):
            spec, count = remove_empty_operations(spec)
            changes["empty_operations_removed"] = count

        # 4. Normalize types
        if norm_config.get("type_standardization", True):
            spec, count = normalize_types(spec)
            changes["types_normalized"] = count

        # 5. Detect circular refs (placeholder)
        if norm_config.get("detect_circular_refs", True):
            spec, count = detect_and_break_circular_refs(spec)
            changes["circular_refs_broken"] = count

        # Save normalized specification
        output_config = config.get("output", {})
        save_spec(
            spec,
            output_path,
            indent=output_config.get("json_indent", 2),
            sort_keys=output_config.get("sort_keys", False),
        )

        return NormalizationResult(
            filename=filename,
            success=True,
            changes=dict(changes),
        )

    except Exception as e:
        return NormalizationResult(
            filename=filename,
            success=False,
            error=str(e),
        )


def process_spec_wrapper(args: tuple) -> NormalizationResult:
    """Wrapper for multiprocessing."""
    spec_path, output_path, config = args
    return normalize_spec_file(spec_path, output_path, config)


def normalize_all_specs(
    input_dir: Path,
    output_dir: Path,
    config: dict,
    parallel: bool = True,
) -> NormalizationStats:
    """Normalize all specification files in a directory.

    Args:
        input_dir: Directory containing enriched specifications.
        output_dir: Directory to save normalized specifications.
        config: Normalization configuration.
        parallel: Enable parallel processing.

    Returns:
        NormalizationStats with processing summary.
    """
    stats = NormalizationStats()

    # Find all JSON spec files
    spec_files = sorted(input_dir.glob("*.json"))
    if not spec_files:
        console.print(f"[yellow]No specification files found in {input_dir}[/yellow]")
        return stats

    console.print(f"[blue]Found {len(spec_files)} specification files to normalize[/blue]")

    # Prepare output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    processing_config = config.get("processing", {})
    workers = processing_config.get("parallel_workers", 4) if parallel else 1
    continue_on_error = processing_config.get("continue_on_error", True)

    # Prepare arguments for processing
    process_args = [(spec_file, output_dir / spec_file.name, config) for spec_file in spec_files]

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Normalizing specifications...", total=len(spec_files))

        if parallel and workers > 1:
            # Parallel processing
            with ProcessPoolExecutor(max_workers=workers) as executor:
                futures = {
                    executor.submit(process_spec_wrapper, args): args[0].name
                    for args in process_args
                }

                for future in as_completed(futures):
                    filename = futures[future]
                    try:
                        result = future.result()
                        _update_stats(stats, result)
                    except Exception as e:
                        stats.files_failed += 1
                        stats.errors.append({"file": filename, "error": str(e)})
                        if not continue_on_error:
                            raise

                    stats.files_processed += 1
                    progress.update(task, advance=1)
        else:
            # Sequential processing
            for args in process_args:
                try:
                    result = process_spec_wrapper(args)
                    _update_stats(stats, result)
                except Exception as e:
                    stats.files_failed += 1
                    stats.errors.append({"file": args[0].name, "error": str(e)})
                    if not continue_on_error:
                        raise

                stats.files_processed += 1
                progress.update(task, advance=1)

    return stats


def _update_stats(stats: NormalizationStats, result: NormalizationResult) -> None:
    """Update statistics from a normalization result."""
    if result.success:
        stats.files_succeeded += 1
        stats.orphan_refs_fixed += result.changes.get("orphan_refs_fixed", 0)
        stats.empty_operations_removed += result.changes.get("empty_operations_removed", 0)
        stats.missing_components_created += result.changes.get("orphan_refs_fixed", 0)
        stats.types_normalized += result.changes.get("types_normalized", 0)
        stats.circular_refs_broken += result.changes.get("circular_refs_broken", 0)
    else:
        stats.files_failed += 1
        if result.error:
            stats.errors.append({"file": result.filename, "error": result.error})


def generate_report(stats: NormalizationStats, output_path: Path) -> None:
    """Generate normalization report."""
    report = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "summary": {
            "files_processed": stats.files_processed,
            "files_succeeded": stats.files_succeeded,
            "files_failed": stats.files_failed,
            "orphan_refs_fixed": stats.orphan_refs_fixed,
            "empty_operations_removed": stats.empty_operations_removed,
            "missing_components_created": stats.missing_components_created,
            "types_normalized": stats.types_normalized,
            "circular_refs_broken": stats.circular_refs_broken,
        },
        "errors": stats.errors,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as f:
        json.dump(report, f, indent=2)
        f.write("\n")

    console.print(f"[green]Report saved to {output_path}[/green]")


def print_summary(stats: NormalizationStats) -> None:
    """Print normalization summary to console."""
    table = Table(title="Normalization Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Files Processed", str(stats.files_processed))
    table.add_row("Files Succeeded", str(stats.files_succeeded))
    table.add_row("Files Failed", str(stats.files_failed))
    table.add_row("Orphan $refs Fixed", str(stats.orphan_refs_fixed))
    table.add_row("Empty Operations Removed", str(stats.empty_operations_removed))
    table.add_row("Missing Components Created", str(stats.missing_components_created))
    table.add_row("Types Normalized", str(stats.types_normalized))

    console.print(table)

    if stats.errors:
        console.print(f"\n[red]Errors ({len(stats.errors)}):[/red]")
        for error in stats.errors[:10]:
            console.print(f"  - {error['file']}: {error['error'][:100]}...")
        if len(stats.errors) > 10:
            console.print(f"  ... and {len(stats.errors) - 10} more errors")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Normalize F5 XC API specifications for UI compatibility",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/normalization.yaml"),
        help="Path to configuration file",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        help="Override input directory for enriched specs",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Override output directory for normalized specs",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        help="Override directory for reports",
    )
    parser.add_argument(
        "--no-parallel",
        action="store_true",
        help="Disable parallel processing",
    )
    parser.add_argument(
        "--workers",
        type=int,
        help="Number of parallel workers",
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
    input_dir = args.input_dir or Path(config["paths"]["enriched"])
    output_dir = args.output_dir or Path(config["paths"]["normalized"])
    report_dir = args.report_dir or Path(config["paths"]["reports"])

    # Override workers if specified
    if args.workers:
        config["processing"]["parallel_workers"] = args.workers

    console.print("[bold blue]F5 XC API Specification Normalization[/bold blue]")
    console.print(f"  Input:  {input_dir}")
    console.print(f"  Output: {output_dir}")

    if not input_dir.exists():
        console.print(f"[red]Input directory not found: {input_dir}[/red]")
        console.print(
            "[yellow]Run 'python -m scripts.enrich' first to enrich specifications[/yellow]",
        )
        return 1

    if args.dry_run:
        console.print("\n[yellow]DRY RUN - analyzing without writing output[/yellow]")
        # In dry-run mode, still process but don't save
        # For now, just list orphan refs
        spec_files = sorted(input_dir.glob("*.json"))
        total_orphans = 0
        for spec_file in spec_files:
            spec = load_spec(spec_file)
            orphans = find_orphan_refs(spec)
            if orphans:
                console.print(f"[yellow]{spec_file.name}: {len(orphans)} orphan refs[/yellow]")
                total_orphans += len(orphans)
        console.print(f"\n[blue]Total orphan refs found: {total_orphans}[/blue]")
        return 0

    # Run normalization pipeline
    stats = normalize_all_specs(
        input_dir=input_dir,
        output_dir=output_dir,
        config=config,
        parallel=not args.no_parallel,
    )

    # Generate report
    report_path = report_dir / "normalization-report.json"
    generate_report(stats, report_path)

    # Print summary
    print_summary(stats)

    # Exit with error if any files failed
    if stats.files_failed > 0:
        console.print(f"\n[yellow]Completed with {stats.files_failed} failures[/yellow]")
        return 1 if not config.get("processing", {}).get("continue_on_error", True) else 0

    console.print(
        f"\n[bold green]Successfully normalized {stats.files_succeeded} specifications![/bold green]",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

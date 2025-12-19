#!/usr/bin/env python3
"""Automated enrichment pipeline for F5 XC API specifications.

Applies acronym normalization, grammar improvements, and branding transformations
to all OpenAPI specification files. Fully automated - no manual intervention required.
"""

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from openapi_spec_validator import validate
from openapi_spec_validator.validation.exceptions import OpenAPIValidationError
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from scripts.utils import AcronymNormalizer, BrandingTransformer, BrandingValidator, GrammarImprover

console = Console()


# Default configuration
DEFAULT_CONFIG = {
    "paths": {
        "original": "specs/original",
        "enriched": "specs/enriched",
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
    "validation": {
        "validate_after_enrichment": True,
        "fail_on_error": False,
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
class EnrichmentStats:
    """Statistics for enrichment processing."""

    files_processed: int = 0
    files_succeeded: int = 0
    files_failed: int = 0
    acronyms_normalized: int = 0
    grammar_improved: int = 0
    branding_transformed: int = 0
    validation_passed: int = 0
    validation_failed: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class EnrichmentResult:
    """Result of enriching a single specification file."""

    filename: str
    success: bool
    changes: dict[str, int] = field(default_factory=dict)
    validation_passed: bool = True
    error: str | None = None


def load_config(config_path: Path | None = None) -> dict:
    """Load configuration from YAML file or use defaults."""
    if config_path and config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
            # Deep merge with defaults
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
    with open(spec_path) as f:
        return json.load(f)


def save_spec(spec: dict[str, Any], output_path: Path, indent: int = 2, sort_keys: bool = False) -> None:
    """Save an OpenAPI specification to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(spec, f, indent=indent, sort_keys=sort_keys, ensure_ascii=False)


def validate_spec(spec: dict[str, Any]) -> tuple[bool, str | None]:
    """Validate an OpenAPI specification."""
    try:
        validate(spec)
        return True, None
    except OpenAPIValidationError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Validation error: {e}"


def count_text_fields(spec: dict[str, Any], target_fields: list[str]) -> int:
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


def enrich_spec_file(
    spec_path: Path,
    output_path: Path,
    config: dict,
) -> EnrichmentResult:
    """Enrich a single specification file.

    Args:
        spec_path: Path to the original specification file.
        output_path: Path to save the enriched specification.
        config: Enrichment configuration.

    Returns:
        EnrichmentResult with processing details.
    """
    filename = spec_path.name

    try:
        # Load specification
        spec = load_spec(spec_path)
        original_field_count = count_text_fields(spec, config.get("target_fields", []))

        # Initialize enrichment utilities
        acronym_normalizer = AcronymNormalizer()
        branding_transformer = BrandingTransformer()

        grammar_config = config.get("grammar", {})
        grammar_improver = GrammarImprover(
            capitalize_sentences=grammar_config.get("capitalize_sentences", True),
            ensure_punctuation=grammar_config.get("ensure_punctuation", True),
            normalize_whitespace=grammar_config.get("normalize_whitespace", True),
            fix_double_spaces=grammar_config.get("fix_double_spaces", True),
            trim_whitespace=grammar_config.get("trim_whitespace", True),
            use_language_tool=True,
        )

        target_fields = config.get("target_fields", ["description", "summary", "title", "x-displayname"])

        # Apply enrichments in order
        # 1. Branding transformations first (most specific)
        spec = branding_transformer.transform_spec(spec, target_fields)

        # 2. Acronym normalization
        spec = acronym_normalizer.normalize_spec(spec, target_fields)

        # 3. Grammar improvements last (most general)
        spec = grammar_improver.improve_spec(spec, target_fields)

        # Close grammar improver resources
        grammar_improver.close()

        # Validate branding was applied correctly
        branding_validator = BrandingValidator()
        legacy_findings = branding_validator.validate_spec(spec, target_fields)

        # Validate enriched spec
        validation_config = config.get("validation", {})
        validation_passed = True
        validation_error = None

        if validation_config.get("validate_after_enrichment", True):
            validation_passed, validation_error = validate_spec(spec)

        # Save enriched specification
        output_config = config.get("output", {})
        save_spec(
            spec,
            output_path,
            indent=output_config.get("json_indent", 2),
            sort_keys=output_config.get("sort_keys", False),
        )

        return EnrichmentResult(
            filename=filename,
            success=True,
            changes={
                "text_fields_processed": original_field_count,
                "legacy_branding_remaining": len(legacy_findings),
            },
            validation_passed=validation_passed,
            error=validation_error if not validation_passed else None,
        )

    except Exception as e:
        return EnrichmentResult(
            filename=filename,
            success=False,
            error=str(e),
            validation_passed=False,
        )


def process_spec_wrapper(args: tuple) -> EnrichmentResult:
    """Wrapper for multiprocessing."""
    spec_path, output_path, config = args
    return enrich_spec_file(spec_path, output_path, config)


def enrich_all_specs(
    input_dir: Path,
    output_dir: Path,
    config: dict,
    parallel: bool = True,
) -> EnrichmentStats:
    """Enrich all specification files in a directory.

    Args:
        input_dir: Directory containing original specifications.
        output_dir: Directory to save enriched specifications.
        config: Enrichment configuration.
        parallel: Enable parallel processing.

    Returns:
        EnrichmentStats with processing summary.
    """
    stats = EnrichmentStats()

    # Find all JSON spec files
    spec_files = sorted(input_dir.glob("*.json"))
    if not spec_files:
        console.print(f"[yellow]No specification files found in {input_dir}[/yellow]")
        return stats

    console.print(f"[blue]Found {len(spec_files)} specification files to enrich[/blue]")

    # Prepare output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    processing_config = config.get("processing", {})
    workers = processing_config.get("parallel_workers", 4) if parallel else 1
    continue_on_error = processing_config.get("continue_on_error", True)

    # Prepare arguments for processing
    process_args = [
        (spec_file, output_dir / spec_file.name, config)
        for spec_file in spec_files
    ]

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Enriching specifications...", total=len(spec_files))

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


def _update_stats(stats: EnrichmentStats, result: EnrichmentResult) -> None:
    """Update statistics from an enrichment result."""
    if result.success:
        stats.files_succeeded += 1
        if result.validation_passed:
            stats.validation_passed += 1
        else:
            stats.validation_failed += 1
            if result.error:
                stats.errors.append({"file": result.filename, "error": result.error})
    else:
        stats.files_failed += 1
        if result.error:
            stats.errors.append({"file": result.filename, "error": result.error})


def generate_report(stats: EnrichmentStats, output_path: Path) -> None:
    """Generate enrichment report."""
    report = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "files_processed": stats.files_processed,
            "files_succeeded": stats.files_succeeded,
            "files_failed": stats.files_failed,
            "validation_passed": stats.validation_passed,
            "validation_failed": stats.validation_failed,
        },
        "errors": stats.errors,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)

    console.print(f"[green]Report saved to {output_path}[/green]")


def print_summary(stats: EnrichmentStats) -> None:
    """Print enrichment summary to console."""
    table = Table(title="Enrichment Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Files Processed", str(stats.files_processed))
    table.add_row("Files Succeeded", str(stats.files_succeeded))
    table.add_row("Files Failed", str(stats.files_failed))
    table.add_row("Validation Passed", str(stats.validation_passed))
    table.add_row("Validation Failed", str(stats.validation_failed))

    console.print(table)

    if stats.errors:
        console.print(f"\n[red]Errors ({len(stats.errors)}):[/red]")
        for error in stats.errors[:10]:  # Show first 10 errors
            console.print(f"  - {error['file']}: {error['error'][:100]}...")
        if len(stats.errors) > 10:
            console.print(f"  ... and {len(stats.errors) - 10} more errors")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Enrich F5 XC API specifications with automated improvements",
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
        "--validate-only",
        action="store_true",
        help="Only validate existing enriched specs",
    )

    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config)

    # Determine directories
    input_dir = args.input_dir or Path(config["paths"]["original"])
    output_dir = args.output_dir or Path(config["paths"]["enriched"])
    report_dir = args.report_dir or Path(config["paths"]["reports"])

    # Override workers if specified
    if args.workers:
        config["processing"]["parallel_workers"] = args.workers

    console.print(f"[bold blue]F5 XC API Specification Enrichment[/bold blue]")
    console.print(f"  Input:  {input_dir}")
    console.print(f"  Output: {output_dir}")

    if not input_dir.exists():
        console.print(f"[red]Input directory not found: {input_dir}[/red]")
        console.print("[yellow]Run 'python scripts/download.py' first to download specifications[/yellow]")
        return 1

    if args.validate_only:
        # Just validate existing enriched specs
        console.print("\n[blue]Validating existing enriched specifications...[/blue]")
        spec_files = sorted(output_dir.glob("*.json"))
        passed = 0
        failed = 0
        for spec_file in spec_files:
            try:
                spec = load_spec(spec_file)
                valid, error = validate_spec(spec)
                if valid:
                    passed += 1
                else:
                    failed += 1
                    console.print(f"[red]Invalid: {spec_file.name}: {error}[/red]")
            except Exception as e:
                failed += 1
                console.print(f"[red]Error: {spec_file.name}: {e}[/red]")
        console.print(f"\n[green]Passed: {passed}[/green], [red]Failed: {failed}[/red]")
        return 0 if failed == 0 else 1

    # Run enrichment pipeline
    stats = enrich_all_specs(
        input_dir=input_dir,
        output_dir=output_dir,
        config=config,
        parallel=not args.no_parallel,
    )

    # Generate report
    report_path = report_dir / "enrichment-report.json"
    generate_report(stats, report_path)

    # Print summary
    print_summary(stats)

    # Exit with error if any files failed
    if stats.files_failed > 0:
        console.print(f"\n[yellow]Completed with {stats.files_failed} failures[/yellow]")
        return 1 if not config.get("processing", {}).get("continue_on_error", True) else 0

    console.print(f"\n[bold green]Successfully enriched {stats.files_succeeded} specifications![/bold green]")
    return 0


if __name__ == "__main__":
    sys.exit(main())

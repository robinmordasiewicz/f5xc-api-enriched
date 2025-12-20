#!/usr/bin/env python3
"""Constraint Analysis CLI.

Compares published API specifications with discovered real-world constraints,
generating reports and recommendations for specification improvements.

Usage:
    python -m scripts.analyze_constraints                    # Full analysis
    python -m scripts.analyze_constraints --output reports/  # Custom output dir
    python -m scripts.analyze_constraints --format json      # JSON output
    python -m scripts.analyze_constraints --format both      # Both MD and JSON
"""

import argparse
import json
import sys
from pathlib import Path

import yaml
from rich.console import Console
from rich.table import Table

from .utils.constraint_analyzer import ConstraintAnalyzer

console = Console()


def load_spec(spec_path: Path) -> dict:
    """Load an OpenAPI specification from file.

    Args:
        spec_path: Path to specification file

    Returns:
        Parsed specification dictionary
    """
    if not spec_path.exists():
        return {}

    with spec_path.open() as f:
        if spec_path.suffix == ".yaml" or spec_path.suffix == ".yml":
            return yaml.safe_load(f) or {}
        return json.load(f)


def load_config(config_path: Path) -> dict:
    """Load configuration from YAML file.

    Args:
        config_path: Path to configuration file

    Returns:
        Configuration dictionary
    """
    if not config_path.exists():
        return {}

    with config_path.open() as f:
        return yaml.safe_load(f) or {}


def print_summary(analyzer: ConstraintAnalyzer) -> None:
    """Print analysis summary to console.

    Args:
        analyzer: Completed constraint analyzer
    """
    report = analyzer.report

    table = Table(title="Constraint Analysis Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Total Fields Analyzed", str(report.total_fields_analyzed))
    table.add_row("Fields with Differences", str(report.fields_with_diffs))
    table.add_row("Tighter Constraints Found", str(report.tighter_constraints_found))
    table.add_row("New Constraints Found", str(report.new_constraints_found))
    table.add_row("Undocumented Fields", str(report.undocumented_fields_found))

    console.print(table)

    # Show top tighter constraints
    if report.tighter_constraints:
        console.print("\n[bold yellow]Top Tighter Constraints:[/bold yellow]")
        for c in report.tighter_constraints[:5]:
            console.print(
                f"  • {c.field_name}.{c.constraint_type}: "
                f"{c.published_value} → {c.discovered_value}",
            )

    # Show top new constraints
    if report.new_constraints:
        console.print("\n[bold green]Top New Constraints:[/bold green]")
        for c in report.new_constraints[:5]:
            value = c.discovered_value
            if isinstance(value, list):
                value = f"[{len(value)} values]"
            elif isinstance(value, str) and len(value) > 30:
                value = value[:30] + "..."
            console.print(f"  • {c.field_name}.{c.constraint_type}: {value}")

    # Show undocumented fields
    if report.undocumented_fields:
        console.print("\n[bold blue]Undocumented Fields:[/bold blue]")
        for field in report.undocumented_fields[:5]:
            console.print(f"  • {field}")
        if len(report.undocumented_fields) > 5:
            console.print(f"  ... and {len(report.undocumented_fields) - 5} more")


def main() -> int:
    """Main entry point for constraint analysis CLI."""
    parser = argparse.ArgumentParser(
        description="Analyze API constraints between published and discovered specs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--published",
        type=Path,
        default=Path("docs/specifications/api/openapi.json"),
        help="Path to published OpenAPI spec (default: docs/specifications/api/openapi.json)",
    )
    parser.add_argument(
        "--discovered",
        type=Path,
        default=Path("specs/discovered/openapi.json"),
        help="Path to discovered OpenAPI spec (default: specs/discovered/openapi.json)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/discovery_enrichment.yaml"),
        help="Path to configuration file",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("reports"),
        help="Output directory for reports (default: reports)",
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "json", "both"],
        default="both",
        help="Output format (default: both)",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress console output",
    )

    args = parser.parse_args()

    # Validate inputs
    if not args.published.exists():
        console.print(f"[red]Error: Published spec not found: {args.published}[/red]")
        console.print("[yellow]Run 'make build' first to generate published specs[/yellow]")
        return 1

    if not args.discovered.exists():
        console.print(f"[red]Error: Discovered spec not found: {args.discovered}[/red]")
        console.print("[yellow]Run 'make discover' first to generate discovered specs[/yellow]")
        return 1

    # Load specs
    if not args.quiet:
        console.print("[bold blue]Constraint Analysis[/bold blue]")
        console.print(f"  Published: {args.published}")
        console.print(f"  Discovered: {args.discovered}")

    published_spec = load_spec(args.published)
    discovered_spec = load_spec(args.discovered)

    if not published_spec:
        console.print("[red]Error: Failed to load published spec[/red]")
        return 1

    if not discovered_spec:
        console.print("[red]Error: Failed to load discovered spec[/red]")
        return 1

    # Load config
    config = load_config(args.config)

    # Run analysis
    if not args.quiet:
        console.print("\n[blue]Analyzing constraints...[/blue]")

    analyzer = ConstraintAnalyzer(config)
    analyzer.analyze(published_spec, discovered_spec)

    # Generate reports
    args.output.mkdir(parents=True, exist_ok=True)
    generated_files = []

    if args.format in ["markdown", "both"]:
        md_path = analyzer.generate_markdown_report(
            args.output / "constraint-analysis.md",
        )
        generated_files.append(md_path)

    if args.format in ["json", "both"]:
        json_path = analyzer.generate_json_report(
            args.output / "constraint-analysis.json",
        )
        generated_files.append(json_path)

    # Print summary
    if not args.quiet:
        print_summary(analyzer)

        console.print("\n[green]Reports generated:[/green]")
        for file_path in generated_files:
            console.print(f"  {file_path}")

    # Return exit code based on findings
    if analyzer.report.tighter_constraints_found > 0:
        if not args.quiet:
            console.print(
                "\n[yellow]Warning: Found constraints that could be tightened[/yellow]",
            )
        return 0  # Still success, just informational

    if not args.quiet:
        console.print("\n[bold green]Analysis complete![/bold green]")

    return 0


if __name__ == "__main__":
    sys.exit(main())

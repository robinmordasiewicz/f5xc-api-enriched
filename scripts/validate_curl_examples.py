#!/usr/bin/env python3
"""Validate curl examples by executing CRUD operations against live F5 XC API.

This script tests the curl examples from config/minimum_configs.yaml by
executing actual Create, Read, Update, Delete operations against the API.

Environment variables:
    F5XC_API_URL: API base URL (required)
    F5XC_API_TOKEN: API authentication token (required)
    F5XC_TEST_NAMESPACE: Override test namespace (optional, default: "default")

Examples:
    # Full CRUD validation
    python scripts/validate_curl_examples.py

    # Dry-run mode (parse and validate without executing)
    python scripts/validate_curl_examples.py --dry-run

    # Test specific resource only
    python scripts/validate_curl_examples.py --resource http_loadbalancer

    # Cleanup orphaned test resources
    python scripts/validate_curl_examples.py --cleanup-only
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "utils"))
from curl_validator import (
    CurlExampleValidator,
    ValidationReport,
    generate_json_report,
    generate_markdown_report,
)

console = Console()


def get_api_url() -> str | None:
    """Get API URL from environment."""
    return os.environ.get("F5XC_API_URL")


def get_api_token() -> str | None:
    """Get API token from environment."""
    return os.environ.get("F5XC_API_TOKEN")


def get_namespace() -> str:
    """Get test namespace from environment or default."""
    return os.environ.get("F5XC_TEST_NAMESPACE", "default")


def print_summary(report: ValidationReport) -> None:
    """Print validation summary to console."""
    table = Table(title="CRUD Validation Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Total Resources", str(report.total_resources))
    table.add_row("Passed", f"[green]{report.passed}[/green]")
    table.add_row("Failed", f"[red]{report.failed}[/red]" if report.failed else "0")
    table.add_row("Skipped", str(report.skipped))
    table.add_row("Duration", f"{report.duration_seconds:.1f}s")
    table.add_row("Dry Run", "Yes" if report.dry_run else "No")

    console.print(table)

    # Print individual results
    if report.results:
        console.print("\n[bold]Results by Resource:[/bold]")
        for result in report.results:
            if result.full_success:
                console.print(f"  [green]✅ {result.resource_type}[/green]")
            elif result.partial_success:
                console.print(f"  [yellow]⚠️  {result.resource_type}[/yellow] (partial)")
                for error in result.errors[:2]:
                    console.print(f"      [dim]{error}[/dim]")
            else:
                console.print(f"  [red]❌ {result.resource_type}[/red]")
                for error in result.errors[:2]:
                    console.print(f"      [dim]{error}[/dim]")

    # Print global errors
    if report.errors:
        console.print("\n[bold red]Errors:[/bold red]")
        for error in report.errors:
            console.print(f"  [red]• {error}[/red]")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate curl examples by executing CRUD operations against live F5 XC API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables:
  F5XC_API_URL         API base URL (required for non-dry-run)
  F5XC_API_TOKEN       API authentication token (required for non-dry-run)
  F5XC_TEST_NAMESPACE  Override test namespace (default: "default")

Examples:
  # Full CRUD validation
  %(prog)s

  # Dry-run mode
  %(prog)s --dry-run

  # Test specific resource
  %(prog)s --resource http_loadbalancer

  # Cleanup orphaned test resources
  %(prog)s --cleanup-only
        """,
    )
    parser.add_argument(
        "--specs-dir",
        type=Path,
        default=Path("docs/specifications/api"),
        help="Directory containing enriched specifications",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/curl_validation.yaml"),
        help="Path to validation configuration file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/curl-validation-report"),
        help="Base path for output reports (will generate .json and .md)",
    )
    parser.add_argument(
        "--namespace",
        type=str,
        default=None,
        help="Namespace for test resources (default: from env or 'default')",
    )
    parser.add_argument(
        "--resource",
        type=str,
        action="append",
        dest="resources",
        help="Specific resource type(s) to test (can specify multiple)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and validate configuration without executing API calls",
    )
    parser.add_argument(
        "--cleanup-only",
        action="store_true",
        help="Only cleanup orphaned test resources (prefix: curl-test-*)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    console.print("[bold blue]F5 XC curl Example CRUD Validation[/bold blue]")

    # Get credentials
    api_url = get_api_url()
    api_token = get_api_token()
    namespace = args.namespace or get_namespace()

    # For non-dry-run, we need credentials
    if not args.dry_run:
        if not api_url:
            console.print("[red]Error: F5XC_API_URL environment variable not set[/red]")
            console.print("[dim]Set F5XC_API_URL to your F5 XC API endpoint[/dim]")
            return 1

        if not api_token:
            console.print("[red]Error: F5XC_API_TOKEN environment variable not set[/red]")
            console.print("[dim]Set F5XC_API_TOKEN to your API authentication token[/dim]")
            return 1

        console.print(f"  API URL:   {api_url}")
        console.print(f"  Namespace: {namespace}")
    else:
        # For dry run, use dummy values
        api_url = api_url or "https://example.console.ves.volterra.io"
        api_token = api_token or "dummy-token"
        console.print("  [dim]Mode: Dry-run (no API calls)[/dim]")

    # Create validator
    validator = CurlExampleValidator(
        specs_dir=args.specs_dir,
        api_url=api_url,
        api_token=api_token,
        namespace=namespace,
        dry_run=args.dry_run,
        config_path=args.config,
    )

    # Cleanup only mode
    if args.cleanup_only:
        console.print("\n[bold]Cleaning up orphaned test resources...[/bold]")
        cleaned = asyncio.run(validator.cleanup_test_resources())
        console.print(f"[green]Cleaned up {cleaned} test resources[/green]")
        return 0

    # Run validation
    console.print("\n[bold]Running CRUD validation...[/bold]")

    report = asyncio.run(validator.validate_all(resource_filter=args.resources))

    # Generate reports
    json_path = args.output.with_suffix(".json")
    md_path = args.output.with_suffix(".md")

    generate_json_report(report, json_path)
    generate_markdown_report(report, md_path)

    console.print("\n[dim]Reports generated:[/dim]")
    console.print(f"  JSON:     {json_path}")
    console.print(f"  Markdown: {md_path}")

    # Print summary
    console.print()
    print_summary(report)

    # Exit code based on results
    if report.failed > 0:
        console.print(
            f"\n[bold red]Validation failed: {report.failed} resource(s) failed[/bold red]",
        )
        return 1

    if report.passed == 0 and report.total_resources > 0:
        console.print(
            "\n[bold yellow]Warning: No resources were successfully validated[/bold yellow]",
        )
        return 1

    console.print("\n[bold green]Validation complete![/bold green]")
    return 0


if __name__ == "__main__":
    sys.exit(main())

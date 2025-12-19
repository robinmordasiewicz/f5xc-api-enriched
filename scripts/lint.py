#!/usr/bin/env python3
"""Lint OpenAPI specifications using Spectral.

Validates specifications against OpenAPI standards and custom rules before merge.
Generates detailed lint reports for quality assurance.

Requires: npm install -g @stoplight/spectral-cli
"""

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

console = Console()


# Default configuration
DEFAULT_CONFIG = {
    "paths": {
        "normalized": "specs/enriched/individual",
        "reports": "reports",
        "ruleset": "config/spectral.yaml",
    },
    "linting": {
        "fail_on_error": False,
        "fail_on_warning": False,
        "skip_on_lint_failure": True,
        "max_errors_per_file": 100,
    },
    "spectral": {
        "format": "json",
        "verbose": False,
    },
}


@dataclass
class LintIssue:
    """A single linting issue."""

    code: str
    message: str
    path: list[str]
    severity: int  # 0=error, 1=warn, 2=info, 3=hint
    range_start: dict[str, int] | None = None
    range_end: dict[str, int] | None = None

    @property
    def severity_name(self) -> str:
        """Return human-readable severity name."""
        return {0: "error", 1: "warning", 2: "info", 3: "hint"}.get(self.severity, "unknown")


@dataclass
class LintResult:
    """Result of linting a single specification file."""

    filename: str
    success: bool
    errors: int = 0
    warnings: int = 0
    infos: int = 0
    hints: int = 0
    issues: list[LintIssue] = field(default_factory=list)
    error_message: str | None = None


@dataclass
class LintStats:
    """Aggregate linting statistics."""

    files_processed: int = 0
    files_passed: int = 0
    files_failed: int = 0
    total_errors: int = 0
    total_warnings: int = 0
    total_infos: int = 0
    total_hints: int = 0
    results: list[LintResult] = field(default_factory=list)


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


def check_spectral_installed() -> bool:
    """Check if Spectral CLI is installed."""
    return shutil.which("spectral") is not None


def run_spectral(
    spec_path: Path,
    ruleset_path: Path | None = None,
) -> tuple[bool, list[dict[str, Any]], str | None]:
    """Run Spectral linter on a specification file.

    Returns (success, issues, error_message).
    """
    cmd = ["spectral", "lint", str(spec_path), "--format", "json"]

    if ruleset_path and ruleset_path.exists():
        cmd.extend(["--ruleset", str(ruleset_path)])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

        # Parse JSON output
        if result.stdout.strip():
            try:
                issues = json.loads(result.stdout)
                return result.returncode == 0, issues, None
            except json.JSONDecodeError:
                return False, [], f"Failed to parse Spectral output: {result.stdout[:200]}"

        # Empty output means no issues
        if result.returncode == 0:
            return True, [], None

        # Non-zero return code with no JSON output
        return False, [], result.stderr or "Spectral returned non-zero exit code"

    except subprocess.TimeoutExpired:
        return False, [], "Spectral timed out after 60 seconds"
    except FileNotFoundError:
        return (
            False,
            [],
            "Spectral CLI not found. Install with: npm install -g @stoplight/spectral-cli",
        )
    except Exception as e:
        return False, [], str(e)


def parse_spectral_issues(raw_issues: list[dict[str, Any]]) -> list[LintIssue]:
    """Parse Spectral output into LintIssue objects."""
    issues = []

    for item in raw_issues:
        issue = LintIssue(
            code=item.get("code", "unknown"),
            message=item.get("message", ""),
            path=item.get("path", []),
            severity=item.get("severity", 1),
            range_start=item.get("range", {}).get("start"),
            range_end=item.get("range", {}).get("end"),
        )
        issues.append(issue)

    return issues


def lint_spec_file(
    spec_path: Path,
    ruleset_path: Path | None,
    config: dict,
) -> LintResult:
    """Lint a single specification file.

    Args:
        spec_path: Path to the specification file.
        ruleset_path: Path to Spectral ruleset file.
        config: Linting configuration.

    Returns:
        LintResult with linting details.
    """
    filename = spec_path.name

    _success, raw_issues, error = run_spectral(spec_path, ruleset_path)

    if error:
        return LintResult(
            filename=filename,
            success=False,
            error_message=error,
        )

    issues = parse_spectral_issues(raw_issues)

    # Count by severity
    errors = sum(1 for i in issues if i.severity == 0)
    warnings = sum(1 for i in issues if i.severity == 1)
    infos = sum(1 for i in issues if i.severity == 2)
    hints = sum(1 for i in issues if i.severity == 3)

    # Determine success based on config
    lint_config = config.get("linting", {})
    passed = True

    if lint_config.get("fail_on_error", False) and errors > 0:
        passed = False
    if lint_config.get("fail_on_warning", False) and warnings > 0:
        passed = False

    # Limit issues if configured
    max_issues = lint_config.get("max_errors_per_file", 100)
    if len(issues) > max_issues:
        issues = issues[:max_issues]

    return LintResult(
        filename=filename,
        success=passed,
        errors=errors,
        warnings=warnings,
        infos=infos,
        hints=hints,
        issues=issues,
    )


def lint_all_specs(
    input_dir: Path,
    ruleset_path: Path | None,
    config: dict,
) -> LintStats:
    """Lint all specification files in a directory.

    Args:
        input_dir: Directory containing specifications.
        ruleset_path: Path to Spectral ruleset file.
        config: Linting configuration.

    Returns:
        LintStats with aggregate results.
    """
    stats = LintStats()

    # Find all JSON spec files
    spec_files = sorted(input_dir.glob("*.json"))
    if not spec_files:
        console.print(f"[yellow]No specification files found in {input_dir}[/yellow]")
        return stats

    console.print(f"[blue]Found {len(spec_files)} specification files to lint[/blue]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Linting specifications...", total=len(spec_files))

        for spec_file in spec_files:
            result = lint_spec_file(spec_file, ruleset_path, config)
            stats.results.append(result)

            stats.files_processed += 1
            if result.success:
                stats.files_passed += 1
            else:
                stats.files_failed += 1

            stats.total_errors += result.errors
            stats.total_warnings += result.warnings
            stats.total_infos += result.infos
            stats.total_hints += result.hints

            progress.update(task, advance=1)

    return stats


def generate_report(stats: LintStats, output_path: Path) -> None:
    """Generate linting report."""
    report = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "summary": {
            "files_processed": stats.files_processed,
            "files_passed": stats.files_passed,
            "files_failed": stats.files_failed,
            "total_errors": stats.total_errors,
            "total_warnings": stats.total_warnings,
            "total_infos": stats.total_infos,
            "total_hints": stats.total_hints,
        },
        "results": [
            {
                "filename": r.filename,
                "success": r.success,
                "errors": r.errors,
                "warnings": r.warnings,
                "infos": r.infos,
                "hints": r.hints,
                "issues": [
                    {
                        "code": i.code,
                        "message": i.message,
                        "severity": i.severity_name,
                        "path": i.path,
                    }
                    for i in r.issues[:20]  # Limit issues per file in report
                ],
                "error_message": r.error_message,
            }
            for r in stats.results
        ],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as f:
        json.dump(report, f, indent=2)
        f.write("\n")

    console.print(f"[green]Report saved to {output_path}[/green]")


def print_summary(stats: LintStats) -> None:
    """Print linting summary to console."""
    table = Table(title="Linting Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Files Processed", str(stats.files_processed))
    table.add_row("Files Passed", str(stats.files_passed))
    table.add_row("Files Failed", str(stats.files_failed))
    table.add_row("Total Errors", str(stats.total_errors))
    table.add_row("Total Warnings", str(stats.total_warnings))
    table.add_row("Total Infos", str(stats.total_infos))
    table.add_row("Total Hints", str(stats.total_hints))

    console.print(table)

    # Show files with most issues
    if stats.total_errors > 0 or stats.total_warnings > 0:
        problem_files = sorted(
            [r for r in stats.results if r.errors > 0 or r.warnings > 0],
            key=lambda r: r.errors + r.warnings,
            reverse=True,
        )[:10]

        if problem_files:
            console.print("\n[yellow]Files with most issues:[/yellow]")
            for r in problem_files:
                console.print(f"  {r.filename}: {r.errors} errors, {r.warnings} warnings")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Lint F5 XC API specifications using Spectral",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/lint.yaml"),
        help="Path to lint configuration file",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        help="Override input directory for specifications",
    )
    parser.add_argument(
        "--ruleset",
        type=Path,
        help="Override path to Spectral ruleset",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        help="Override directory for reports",
    )
    parser.add_argument(
        "--fail-on-error",
        action="store_true",
        help="Exit with error if any linting errors found",
    )
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="Exit with error if any linting warnings found",
    )

    args = parser.parse_args()

    # Check Spectral installation
    if not check_spectral_installed():
        console.print("[red]Spectral CLI not found![/red]")
        console.print("[yellow]Install with: npm install -g @stoplight/spectral-cli[/yellow]")
        console.print(
            "[yellow]Or skip linting by removing the lint step from the workflow[/yellow]",
        )
        return 1

    # Load configuration
    config = load_config(args.config)

    # Override config from args
    if args.fail_on_error:
        config["linting"]["fail_on_error"] = True
    if args.fail_on_warning:
        config["linting"]["fail_on_warning"] = True

    # Determine paths
    input_dir = args.input_dir or Path(config["paths"]["normalized"])
    ruleset_path = args.ruleset or Path(config["paths"]["ruleset"])
    report_dir = args.report_dir or Path(config["paths"]["reports"])

    console.print("[bold blue]F5 XC API Specification Linting[/bold blue]")
    console.print(f"  Input:   {input_dir}")
    console.print(f"  Ruleset: {ruleset_path}")

    if not input_dir.exists():
        console.print(f"[red]Input directory not found: {input_dir}[/red]")
        console.print(
            "[yellow]Run 'python -m scripts.normalize' first to normalize specifications[/yellow]",
        )
        return 1

    # Check ruleset exists
    if not ruleset_path.exists():
        console.print(f"[yellow]Ruleset not found: {ruleset_path}[/yellow]")
        console.print("[yellow]Using Spectral default rules[/yellow]")
        ruleset_path = None

    # Run linting
    stats = lint_all_specs(input_dir, ruleset_path, config)

    # Generate report
    report_path = report_dir / "lint-report.json"
    generate_report(stats, report_path)

    # Print summary
    print_summary(stats)

    # Determine exit code
    lint_config = config.get("linting", {})
    if lint_config.get("fail_on_error", False) and stats.total_errors > 0:
        console.print(f"\n[red]Failed: {stats.total_errors} linting errors found[/red]")
        return 1
    if lint_config.get("fail_on_warning", False) and stats.total_warnings > 0:
        console.print(f"\n[red]Failed: {stats.total_warnings} linting warnings found[/red]")
        return 1

    if stats.files_failed > 0:
        console.print(f"\n[yellow]Completed with {stats.files_failed} files having issues[/yellow]")
    else:
        console.print(
            f"\n[bold green]All {stats.files_passed} specifications passed linting![/bold green]",
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())

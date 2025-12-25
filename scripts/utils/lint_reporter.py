"""Lint report generator for OpenAPI specification validation.

Extracts report generation logic from lint.py into a reusable reporter class
supporting both JSON and markdown output formats.
"""

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Add utils to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from path_config import PathConfig
from report_base import BaseReporter
from server_variables_markdown import ServerVariablesMarkdownHelper

logger = logging.getLogger(__name__)


@dataclass
class LintIssue:
    """A single linting issue."""

    code: str
    message: str
    path: list[str]
    severity: int  # 0=error, 1=warn, 2=info, 3=hint

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


class LintReporter(BaseReporter):
    """Reporter for lint validation results.

    Generates both JSON and markdown reports with linting statistics and issues.
    """

    def __init__(
        self,
        stats: LintStats,
        path_config: PathConfig | None = None,
    ) -> None:
        """Initialize lint reporter.

        Args:
            stats: LintStats object with linting results
            path_config: Optional PathConfig instance
        """
        super().__init__(
            title="Specification Linting Report",
            description="OpenAPI specification validation using Spectral",
            path_config=path_config,
        )
        self.stats = stats
        self.sv_helper = ServerVariablesMarkdownHelper()

    def to_dict(self) -> dict[str, Any]:
        """Convert linting report to dictionary."""
        return {
            "timestamp": self.generated_at,
            "summary": {
                "files_processed": self.stats.files_processed,
                "files_passed": self.stats.files_passed,
                "files_failed": self.stats.files_failed,
                "total_errors": self.stats.total_errors,
                "total_warnings": self.stats.total_warnings,
                "total_infos": self.stats.total_infos,
                "total_hints": self.stats.total_hints,
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
                        for i in r.issues[:20]  # Limit issues per file
                    ],
                    "error_message": r.error_message,
                }
                for r in self.stats.results
            ],
        }

    def to_markdown(self) -> str:
        """Convert linting report to markdown."""
        md = self.markdown_report_header()

        # Summary section
        md += self.markdown_section(
            "Summary",
            self._markdown_summary_table(),
            level=2,
        )

        # Server variables section
        sv_section = self.sv_helper.render_server_configuration_validation_section()
        if sv_section:
            md += sv_section

        # Issues by severity
        if self.stats.total_errors > 0:
            md += self._markdown_errors_section()

        if self.stats.total_warnings > 0:
            md += self._markdown_warnings_section()

        # Files with issues
        if self.stats.total_errors > 0 or self.stats.total_warnings > 0:
            md += self._markdown_problem_files_section()

        return md

    def _markdown_summary_table(self) -> str:
        """Create markdown summary table."""
        headers = ["Metric", "Count"]
        rows = [
            ["Files Processed", str(self.stats.files_processed)],
            ["Files Passed", str(self.stats.files_passed)],
            ["Files Failed", str(self.stats.files_failed)],
            ["Total Errors", str(self.stats.total_errors)],
            ["Total Warnings", str(self.stats.total_warnings)],
            ["Total Infos", str(self.stats.total_infos)],
            ["Total Hints", str(self.stats.total_hints)],
        ]
        return BaseReporter.markdown_table(headers, rows)

    def _markdown_errors_section(self) -> str:
        """Create section for linting errors."""
        content = ""

        error_files = [r for r in self.stats.results if r.errors > 0]
        if error_files:
            headers = ["File", "Errors", "Issues"]
            rows = []
            for result in error_files[:10]:  # Limit to 10 files
                issue_list = ", ".join(f"{i.code}" for i in result.issues[:5])  # First 5 codes
                rows.append([result.filename, str(result.errors), issue_list])

            content = BaseReporter.markdown_table(headers, rows)

        return self.markdown_section("Errors", content, level=3)

    def _markdown_warnings_section(self) -> str:
        """Create section for linting warnings."""
        content = ""

        warning_files = [r for r in self.stats.results if r.warnings > 0 and not r.success]
        if warning_files:
            headers = ["File", "Warnings", "Issues"]
            rows = []
            for result in warning_files[:10]:  # Limit to 10 files
                issue_list = ", ".join(f"{i.code}" for i in result.issues if i.severity == 1)[
                    :50
                ]  # Limit string length
                rows.append([result.filename, str(result.warnings), issue_list])

            content = BaseReporter.markdown_table(headers, rows)

        return self.markdown_section("Warnings", content, level=3)

    def _markdown_problem_files_section(self) -> str:
        """Create section for files with most issues."""
        problem_files = sorted(
            [r for r in self.stats.results if r.errors > 0 or r.warnings > 0],
            key=lambda r: r.errors + r.warnings,
            reverse=True,
        )[:10]

        if not problem_files:
            return ""

        headers = ["File", "Errors", "Warnings", "Total"]
        rows = []
        for result in problem_files:
            total = result.errors + result.warnings
            rows.append([result.filename, str(result.errors), str(result.warnings), str(total)])

        content = BaseReporter.markdown_table(headers, rows)
        return self.markdown_section("Files with Most Issues", content, level=3)

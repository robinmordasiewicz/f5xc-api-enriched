"""Validation report generator for live API testing.

Extracts report generation logic from validate.py into a reusable reporter class
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
class EndpointResult:
    """Result of validating a single endpoint."""

    path: str
    method: str
    status: str  # available, unavailable, error, skipped
    status_code: int | None = None
    schema_match: bool = True
    response_time_ms: float | None = None
    error: str | None = None
    discrepancies: list[str] = field(default_factory=list)


@dataclass
class SpecValidationResult:
    """Result of validating a single specification."""

    filename: str
    endpoints_total: int = 0
    endpoints_validated: int = 0
    endpoints_available: int = 0
    endpoints_skipped: int = 0
    schema_matches: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class ValidationStats:
    """Aggregate validation statistics."""

    specs_processed: int = 0
    total_endpoints: int = 0
    endpoints_validated: int = 0
    endpoints_available: int = 0
    endpoints_unavailable: int = 0
    schema_matches: int = 0
    spec_results: list[SpecValidationResult] = field(default_factory=list)
    discrepancies: list[dict[str, Any]] = field(default_factory=list)


class ValidationReporter(BaseReporter):
    """Reporter for API validation results.

    Generates both JSON and markdown reports with validation statistics
    and endpoint coverage analysis.
    """

    def __init__(
        self,
        stats: ValidationStats,
        path_config: PathConfig | None = None,
    ) -> None:
        """Initialize validation reporter.

        Args:
            stats: ValidationStats object with validation results
            path_config: Optional PathConfig instance
        """
        super().__init__(
            title="API Validation Report",
            description="Live API endpoint validation and schema compliance testing",
            path_config=path_config,
        )
        self.stats = stats
        self.sv_helper = ServerVariablesMarkdownHelper()

    def to_dict(self) -> dict[str, Any]:
        """Convert validation report to dictionary."""
        availability_percentage = 0.0
        if self.stats.endpoints_validated > 0:
            availability_percentage = round(
                (self.stats.endpoints_available / self.stats.endpoints_validated * 100),
                2,
            )

        schema_match_percentage = 0.0
        if self.stats.endpoints_available > 0:
            schema_match_percentage = round(
                (self.stats.schema_matches / self.stats.endpoints_available * 100),
                2,
            )

        return {
            "timestamp": self.generated_at,
            "summary": {
                "specs_processed": self.stats.specs_processed,
                "total_endpoints": self.stats.total_endpoints,
                "endpoints_validated": self.stats.endpoints_validated,
                "endpoints_available": self.stats.endpoints_available,
                "endpoints_unavailable": self.stats.endpoints_unavailable,
                "schema_matches": self.stats.schema_matches,
                "availability_percentage": availability_percentage,
                "schema_match_percentage": schema_match_percentage,
            },
            "discrepancies": self.stats.discrepancies[:100],  # Limit to first 100
            "specs": [
                {
                    "filename": r.filename,
                    "endpoints_total": r.endpoints_total,
                    "endpoints_validated": r.endpoints_validated,
                    "endpoints_available": r.endpoints_available,
                    "endpoints_skipped": r.endpoints_skipped,
                    "schema_matches": r.schema_matches,
                    "errors": r.errors[:5],
                }
                for r in self.stats.spec_results
            ],
        }

    def to_markdown(self) -> str:
        """Convert validation report to markdown."""
        md = self.markdown_report_header()

        # Summary section
        md += self.markdown_section(
            "Executive Summary",
            self._markdown_summary_table(),
            level=2,
        )

        # Thresholds and metrics
        md += self._markdown_metrics_section()

        # Server variables section
        sv_section = self.sv_helper.render_test_configuration_section()
        if sv_section:
            md += sv_section

        # Specification results
        if self.stats.spec_results:
            md += self._markdown_spec_results_section()

        # Discrepancies
        if self.stats.discrepancies:
            md += self._markdown_discrepancies_section()

        return md

    def _markdown_summary_table(self) -> str:
        """Create markdown summary table."""
        headers = ["Metric", "Value"]
        rows = [
            ["Specifications Processed", str(self.stats.specs_processed)],
            ["Total Endpoints", str(self.stats.total_endpoints)],
            ["Endpoints Validated", str(self.stats.endpoints_validated)],
            ["Endpoints Available", str(self.stats.endpoints_available)],
            ["Endpoints Unavailable", str(self.stats.endpoints_unavailable)],
            ["Schema Matches", str(self.stats.schema_matches)],
        ]

        if self.stats.endpoints_validated > 0:
            availability = round(
                (self.stats.endpoints_available / self.stats.endpoints_validated * 100),
                1,
            )
            rows.append(["Availability %", f"{availability}%"])

        if self.stats.endpoints_available > 0:
            schema_match = round(
                (self.stats.schema_matches / self.stats.endpoints_available * 100),
                1,
            )
            rows.append(["Schema Match %", f"{schema_match}%"])

        return BaseReporter.markdown_table(headers, rows)

    def _markdown_metrics_section(self) -> str:
        """Create section with validation metrics."""
        content = ""

        if self.stats.endpoints_validated > 0:
            availability = round(
                (self.stats.endpoints_available / self.stats.endpoints_validated * 100),
                1,
            )
            content += f"- **Availability**: {availability}% of endpoints available\n"

        if self.stats.endpoints_available > 0:
            schema_match = round(
                (self.stats.schema_matches / self.stats.endpoints_available * 100),
                1,
            )
            content += (
                f"- **Schema Compliance**: {schema_match}% of available endpoints match schema\n"
            )

        content += f"- **Total Endpoints**: {self.stats.total_endpoints}\n"
        content += f"- **Validated**: {self.stats.endpoints_validated}\n"
        content += f"- **Skipped**: {self.stats.total_endpoints - self.stats.endpoints_validated}\n"

        return self.markdown_section("Metrics", content, level=3)

    def _markdown_spec_results_section(self) -> str:
        """Create section with per-spec results."""
        headers = ["Specification", "Endpoints", "Validated", "Available", "Schema Match"]
        rows = [
            [
                result.filename,
                str(result.endpoints_total),
                str(result.endpoints_validated),
                str(result.endpoints_available),
                str(result.schema_matches),
            ]
            for result in self.stats.spec_results
        ]

        content = BaseReporter.markdown_table(headers, rows)
        return self.markdown_section("Specification Results", content, level=3)

    def _markdown_discrepancies_section(self) -> str:
        """Create section documenting discovered discrepancies."""
        if not self.stats.discrepancies:
            return ""

        content = f"Found {len(self.stats.discrepancies)} discrepancies:\n\n"

        for i, disc in enumerate(self.stats.discrepancies[:20], 1):  # First 20
            if isinstance(disc, dict):
                content += f"{i}. {disc.get('description', 'Unknown discrepancy')}\n"
                if "endpoint" in disc:
                    content += f"   - Endpoint: {disc['endpoint']}\n"
                if "issue" in disc:
                    content += f"   - Issue: {disc['issue']}\n"
            else:
                content += f"{i}. {disc!s}\n"

        if len(self.stats.discrepancies) > 20:
            content += f"\n... and {len(self.stats.discrepancies) - 20} more discrepancies\n"

        return self.markdown_section("Discrepancies", content, level=3)

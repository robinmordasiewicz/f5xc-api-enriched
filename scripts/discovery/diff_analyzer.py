"""Schema diff analyzer for comparing published vs discovered APIs.

Compares published OpenAPI specs with discovered behavior to detect:
- Missing fields in published spec
- Extra undocumented fields
- Type mismatches
- Constraint differences
- Default value differences
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .schema_inferrer import InferredSchema


class DiffType(Enum):
    """Types of schema differences."""

    MISSING_FIELD = "missing_field"  # Field in discovered but not published
    EXTRA_FIELD = "extra_field"  # Field in published but not discovered
    TYPE_MISMATCH = "type_mismatch"  # Different types
    FORMAT_MISMATCH = "format_mismatch"  # Different formats
    CONSTRAINT_DIFF = "constraint_diff"  # Different constraints
    ENUM_DIFF = "enum_diff"  # Different enum values
    DEFAULT_DIFF = "default_diff"  # Different defaults
    REQUIRED_DIFF = "required_diff"  # Different required status
    NULLABLE_DIFF = "nullable_diff"  # Different nullable status


class DiffSeverity(Enum):
    """Severity of schema differences."""

    INFO = "info"  # Minor difference, informational
    WARNING = "warning"  # Potential issue
    ERROR = "error"  # Breaking difference


@dataclass
class SchemaDiff:
    """A single schema difference."""

    path: str  # JSON path to the field (e.g., "spec.timeout")
    diff_type: DiffType
    severity: DiffSeverity
    published_value: Any = None
    discovered_value: Any = None
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "path": self.path,
            "type": self.diff_type.value,
            "severity": self.severity.value,
            "published": self.published_value,
            "discovered": self.discovered_value,
            "message": self.message,
        }


@dataclass
class DiffReport:
    """Complete diff report for a schema comparison."""

    endpoint: str
    method: str
    diffs: list[SchemaDiff] = field(default_factory=list)
    published_schema: dict = field(default_factory=dict)
    discovered_schema: dict = field(default_factory=dict)

    @property
    def total_diffs(self) -> int:
        """Total number of differences."""
        return len(self.diffs)

    @property
    def errors(self) -> list[SchemaDiff]:
        """Get error-level differences."""
        return [d for d in self.diffs if d.severity == DiffSeverity.ERROR]

    @property
    def warnings(self) -> list[SchemaDiff]:
        """Get warning-level differences."""
        return [d for d in self.diffs if d.severity == DiffSeverity.WARNING]

    @property
    def has_breaking_changes(self) -> bool:
        """Check if there are breaking changes."""
        return len(self.errors) > 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "endpoint": self.endpoint,
            "method": self.method,
            "total_diffs": self.total_diffs,
            "errors": len(self.errors),
            "warnings": len(self.warnings),
            "diffs": [d.to_dict() for d in self.diffs],
        }


class DiffAnalyzer:
    """Analyze differences between published and discovered schemas.

    Provides:
    - Deep schema comparison
    - Type mismatch detection
    - Constraint comparison
    - Enum and default value comparison
    """

    def __init__(
        self,
        compare_required: bool = True,
        compare_types: bool = True,
        compare_constraints: bool = True,
        compare_enums: bool = True,
        compare_defaults: bool = True,
        ignore_fields: list[str] | None = None,
    ) -> None:
        """Initialize diff analyzer.

        Args:
            compare_required: Compare required field status
            compare_types: Compare field types
            compare_constraints: Compare min/max constraints
            compare_enums: Compare enum values
            compare_defaults: Compare default values
            ignore_fields: Fields to ignore in comparison
        """
        self.compare_required = compare_required
        self.compare_types = compare_types
        self.compare_constraints = compare_constraints
        self.compare_enums = compare_enums
        self.compare_defaults = compare_defaults
        self.ignore_fields = set(ignore_fields or [])

    def compare(
        self,
        published: dict[str, Any],
        discovered: InferredSchema | dict[str, Any],
        endpoint: str = "",
        method: str = "GET",
    ) -> DiffReport:
        """Compare published schema with discovered schema.

        Args:
            published: Published OpenAPI schema
            discovered: Discovered schema (InferredSchema or dict)
            endpoint: Endpoint path for context
            method: HTTP method for context

        Returns:
            DiffReport with all differences
        """
        report = DiffReport(
            endpoint=endpoint,
            method=method,
            published_schema=published,
            discovered_schema=(
                discovered.to_json_schema()
                if isinstance(discovered, InferredSchema)
                else discovered
            ),
        )

        # Convert InferredSchema to dict if needed
        discovered_dict = (
            discovered.to_json_schema() if isinstance(discovered, InferredSchema) else discovered
        )

        # Compare schemas recursively
        self._compare_schemas(
            published,
            discovered_dict,
            path="",
            report=report,
        )

        return report

    def _compare_schemas(
        self,
        published: dict[str, Any],
        discovered: dict[str, Any],
        path: str,
        report: DiffReport,
    ) -> None:
        """Recursively compare two schemas.

        Args:
            published: Published schema dict
            discovered: Discovered schema dict
            path: Current JSON path
            report: Report to add diffs to
        """
        # Check if path should be ignored
        if any(path.endswith(f) for f in self.ignore_fields):
            return

        # Compare types
        if self.compare_types:
            pub_type = self._normalize_type(published.get("type"))
            disc_type = self._normalize_type(discovered.get("type"))

            if pub_type != disc_type:
                report.diffs.append(
                    SchemaDiff(
                        path=path or "root",
                        diff_type=DiffType.TYPE_MISMATCH,
                        severity=DiffSeverity.ERROR,
                        published_value=pub_type,
                        discovered_value=disc_type,
                        message=f"Type mismatch: published '{pub_type}' vs discovered '{disc_type}'",
                    ),
                )

        # Compare formats
        pub_format = published.get("format")
        disc_format = discovered.get("format")

        if pub_format != disc_format and disc_format:
            report.diffs.append(
                SchemaDiff(
                    path=path or "root",
                    diff_type=DiffType.FORMAT_MISMATCH,
                    severity=DiffSeverity.INFO,
                    published_value=pub_format,
                    discovered_value=disc_format,
                    message=f"Format discovered: {disc_format}",
                ),
            )

        # Compare constraints
        if self.compare_constraints:
            self._compare_constraints(published, discovered, path, report)

        # Compare enums
        if self.compare_enums:
            self._compare_enums(published, discovered, path, report)

        # Compare defaults
        if self.compare_defaults:
            self._compare_defaults(published, discovered, path, report)

        # Compare object properties
        pub_props = published.get("properties", {})
        disc_props = discovered.get("properties", {})

        if pub_props or disc_props:
            self._compare_properties(pub_props, disc_props, path, report)

        # Compare required fields
        if self.compare_required:
            pub_required = set(published.get("required", []))
            disc_required = set(discovered.get("required", []))

            for field in disc_required - pub_required:
                field_path = f"{path}.{field}" if path else field
                if not any(field_path.endswith(f) for f in self.ignore_fields):
                    report.diffs.append(
                        SchemaDiff(
                            path=field_path,
                            diff_type=DiffType.REQUIRED_DIFF,
                            severity=DiffSeverity.WARNING,
                            published_value=False,
                            discovered_value=True,
                            message=f"Field '{field}' is required in discovered but not in published",
                        ),
                    )

        # Compare array items
        if published.get("type") == "array" and discovered.get("type") == "array":
            pub_items = published.get("items", {})
            disc_items = discovered.get("items", {})
            if pub_items or disc_items:
                self._compare_schemas(
                    pub_items,
                    disc_items,
                    f"{path}[items]" if path else "[items]",
                    report,
                )

    def _compare_properties(
        self,
        published: dict[str, Any],
        discovered: dict[str, Any],
        path: str,
        report: DiffReport,
    ) -> None:
        """Compare object properties.

        Args:
            published: Published properties dict
            discovered: Discovered properties dict
            path: Current JSON path
            report: Report to add diffs to
        """
        pub_keys = set(published.keys())
        disc_keys = set(discovered.keys())

        # Fields in discovered but not published (undocumented)
        for key in disc_keys - pub_keys:
            field_path = f"{path}.{key}" if path else key
            if not any(field_path.endswith(f) for f in self.ignore_fields):
                report.diffs.append(
                    SchemaDiff(
                        path=field_path,
                        diff_type=DiffType.MISSING_FIELD,
                        severity=DiffSeverity.WARNING,
                        published_value=None,
                        discovered_value=discovered[key],
                        message=f"Undocumented field '{key}' discovered",
                    ),
                )

        # Fields in published but not discovered (may be optional)
        for key in pub_keys - disc_keys:
            field_path = f"{path}.{key}" if path else key
            if not any(field_path.endswith(f) for f in self.ignore_fields):
                report.diffs.append(
                    SchemaDiff(
                        path=field_path,
                        diff_type=DiffType.EXTRA_FIELD,
                        severity=DiffSeverity.INFO,
                        published_value=published[key],
                        discovered_value=None,
                        message=f"Published field '{key}' not seen in responses",
                    ),
                )

        # Compare common fields
        for key in pub_keys & disc_keys:
            field_path = f"{path}.{key}" if path else key
            self._compare_schemas(
                published[key],
                discovered[key],
                field_path,
                report,
            )

    def _compare_constraints(
        self,
        published: dict[str, Any],
        discovered: dict[str, Any],
        path: str,
        report: DiffReport,
    ) -> None:
        """Compare schema constraints.

        Args:
            published: Published schema dict
            discovered: Discovered schema dict
            path: Current JSON path
            report: Report to add diffs to
        """
        constraint_keys = [
            "minLength",
            "maxLength",
            "minimum",
            "maximum",
            "minItems",
            "maxItems",
            "pattern",
        ]

        for key in constraint_keys:
            pub_val = published.get(key)
            disc_val = discovered.get(key)

            if disc_val is not None and pub_val != disc_val:
                report.diffs.append(
                    SchemaDiff(
                        path=path or "root",
                        diff_type=DiffType.CONSTRAINT_DIFF,
                        severity=DiffSeverity.INFO if pub_val is None else DiffSeverity.WARNING,
                        published_value=pub_val,
                        discovered_value=disc_val,
                        message=f"Constraint '{key}' differs: published={pub_val}, discovered={disc_val}",
                    ),
                )

    def _compare_enums(
        self,
        published: dict[str, Any],
        discovered: dict[str, Any],
        path: str,
        report: DiffReport,
    ) -> None:
        """Compare enum values.

        Args:
            published: Published schema dict
            discovered: Discovered schema dict
            path: Current JSON path
            report: Report to add diffs to
        """
        pub_enum = set(published.get("enum", []))
        disc_enum = set(discovered.get("enum", []))

        if not pub_enum and not disc_enum:
            return

        # New enum values discovered
        new_values = disc_enum - pub_enum
        if new_values:
            report.diffs.append(
                SchemaDiff(
                    path=path or "root",
                    diff_type=DiffType.ENUM_DIFF,
                    severity=DiffSeverity.WARNING,
                    published_value=list(pub_enum),
                    discovered_value=list(new_values),
                    message=f"New enum values discovered: {new_values}",
                ),
            )

    def _compare_defaults(
        self,
        published: dict[str, Any],
        discovered: dict[str, Any],
        path: str,
        report: DiffReport,
    ) -> None:
        """Compare default values.

        Args:
            published: Published schema dict
            discovered: Discovered schema dict
            path: Current JSON path
            report: Report to add diffs to
        """
        pub_default = published.get("default")
        disc_default = discovered.get("default")

        if disc_default is not None and pub_default != disc_default:
            report.diffs.append(
                SchemaDiff(
                    path=path or "root",
                    diff_type=DiffType.DEFAULT_DIFF,
                    severity=DiffSeverity.INFO,
                    published_value=pub_default,
                    discovered_value=disc_default,
                    message=f"Default value discovered: {disc_default}",
                ),
            )

    def _normalize_type(self, type_value: Any) -> str | None:
        """Normalize type value for comparison.

        Args:
            type_value: Type from schema (str, list, or None)

        Returns:
            Normalized type string
        """
        if type_value is None:
            return None

        if isinstance(type_value, list):
            # Handle nullable types ["string", "null"]
            non_null = [t for t in type_value if t != "null"]
            return non_null[0] if non_null else "null"

        return type_value

    def generate_summary(self, reports: list[DiffReport]) -> dict[str, Any]:
        """Generate summary from multiple diff reports.

        Args:
            reports: List of diff reports

        Returns:
            Summary dictionary
        """
        total_diffs = sum(r.total_diffs for r in reports)
        total_errors = sum(len(r.errors) for r in reports)
        total_warnings = sum(len(r.warnings) for r in reports)

        # Count by diff type
        type_counts: dict[str, int] = {}
        for report in reports:
            for diff in report.diffs:
                type_name = diff.diff_type.value
                type_counts[type_name] = type_counts.get(type_name, 0) + 1

        return {
            "total_endpoints": len(reports),
            "endpoints_with_diffs": len([r for r in reports if r.total_diffs > 0]),
            "total_diffs": total_diffs,
            "total_errors": total_errors,
            "total_warnings": total_warnings,
            "diff_types": type_counts,
            "has_breaking_changes": any(r.has_breaking_changes for r in reports),
        }

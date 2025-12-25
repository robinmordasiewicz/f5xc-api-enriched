"""Constraint Analyzer Module.

Compares published API constraints with discovered real-world constraints,
generating reports and recommendations for specification improvements.
"""

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Add utils to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from path_config import PathConfig
from report_base import BaseReporter
from server_variables_markdown import ServerVariablesMarkdownHelper


@dataclass
class ConstraintComparison:
    """Comparison between published and discovered constraints."""

    field_name: str
    field_path: str
    constraint_type: str
    published_value: Any = None
    discovered_value: Any = None
    difference: str = ""
    severity: str = "info"  # info, warning, error
    recommendation: str = ""
    sample_size: int = 0
    confidence: float = 0.0


@dataclass
class AnalysisReport:
    """Full constraint analysis report."""

    total_fields_analyzed: int = 0
    fields_with_diffs: int = 0
    tighter_constraints_found: int = 0
    new_constraints_found: int = 0
    undocumented_fields_found: int = 0

    comparisons: list[ConstraintComparison] = field(default_factory=list)
    tighter_constraints: list[ConstraintComparison] = field(default_factory=list)
    new_constraints: list[ConstraintComparison] = field(default_factory=list)
    undocumented_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert report to dictionary."""
        return {
            "summary": {
                "total_fields_analyzed": self.total_fields_analyzed,
                "fields_with_diffs": self.fields_with_diffs,
                "tighter_constraints_found": self.tighter_constraints_found,
                "new_constraints_found": self.new_constraints_found,
                "undocumented_fields_found": self.undocumented_fields_found,
            },
            "tighter_constraints": [
                {
                    "field": c.field_name,
                    "constraint": c.constraint_type,
                    "published": c.published_value,
                    "discovered": c.discovered_value,
                    "recommendation": c.recommendation,
                }
                for c in self.tighter_constraints
            ],
            "new_constraints": [
                {
                    "field": c.field_name,
                    "constraint": c.constraint_type,
                    "value": c.discovered_value,
                    "confidence": c.confidence,
                }
                for c in self.new_constraints
            ],
            "undocumented_fields": self.undocumented_fields,
        }


class ConstraintAnalyzer(BaseReporter):
    """Analyze constraints between published and discovered specs.

    Provides detailed comparison and recommendations for improving
    API specifications based on real-world API behavior.
    """

    def __init__(self, config: dict | None = None, path_config: PathConfig | None = None) -> None:
        """Initialize the constraint analyzer.

        Args:
            config: Optional configuration dictionary
            path_config: Optional PathConfig instance
        """
        super().__init__(
            title="Constraint Analysis Report",
            description="Comparison of published and discovered API constraints",
            path_config=path_config,
        )
        self.config = config or {}
        self.report = AnalysisReport()
        self.sv_helper = ServerVariablesMarkdownHelper()

    def analyze(
        self,
        published_spec: dict,
        discovered_spec: dict,
    ) -> AnalysisReport:
        """Analyze constraints between published and discovered specs.

        Args:
            published_spec: Published OpenAPI specification
            discovered_spec: Discovered OpenAPI specification

        Returns:
            AnalysisReport with all findings
        """
        self.report = AnalysisReport()

        # Extract schemas from both specs
        published_schemas = self._get_schemas(published_spec)
        discovered_schemas = self._get_schemas(discovered_spec)

        # Extract constraints from each
        published_constraints = self._extract_all_constraints(published_schemas)
        discovered_constraints = self._extract_all_constraints(discovered_schemas)

        # Compare constraints
        self._compare_constraints(published_constraints, discovered_constraints)

        # Find undocumented fields
        self._find_undocumented_fields(published_schemas, discovered_schemas)

        return self.report

    def _get_schemas(self, spec: dict) -> dict:
        """Extract component schemas from spec.

        Args:
            spec: OpenAPI specification

        Returns:
            Dictionary of schema definitions
        """
        return spec.get("components", {}).get("schemas", {})

    def _extract_all_constraints(self, schemas: dict) -> dict[str, dict]:
        """Extract all constraints from schemas.

        Args:
            schemas: Schema definitions

        Returns:
            Dictionary mapping field paths to their constraints
        """
        constraints: dict[str, dict] = {}

        def extract_from_schema(schema: dict, path_prefix: str) -> None:
            if not isinstance(schema, dict):
                return

            # Handle properties
            properties = schema.get("properties", {})
            for prop_name, prop_schema in properties.items():
                if not isinstance(prop_schema, dict):
                    continue

                prop_path = f"{path_prefix}/{prop_name}" if path_prefix else prop_name
                prop_constraints = self._extract_property_constraints(prop_schema)

                if prop_constraints:
                    constraints[prop_path] = {
                        "name": prop_name,
                        **prop_constraints,
                    }
                    self.report.total_fields_analyzed += 1

                # Recurse into nested objects
                if prop_schema.get("type") == "object":
                    extract_from_schema(prop_schema, prop_path)

                # Handle array items
                if prop_schema.get("type") == "array" and "items" in prop_schema:
                    items = prop_schema["items"]
                    if isinstance(items, dict):
                        extract_from_schema(items, f"{prop_path}[]")

            # Handle allOf/oneOf/anyOf
            for combiner in ["allOf", "oneOf", "anyOf"]:
                if combiner in schema:
                    for i, sub_schema in enumerate(schema[combiner]):
                        if isinstance(sub_schema, dict):
                            extract_from_schema(sub_schema, path_prefix)

        # Process all schemas
        for schema_name, schema in schemas.items():
            extract_from_schema(schema, schema_name)

        return constraints

    def _extract_property_constraints(self, prop_schema: dict) -> dict:
        """Extract constraints from a property schema.

        Args:
            prop_schema: Property schema definition

        Returns:
            Dictionary of constraints
        """
        constraints = {}

        # String constraints
        if "minLength" in prop_schema:
            constraints["minLength"] = prop_schema["minLength"]
        if "maxLength" in prop_schema:
            constraints["maxLength"] = prop_schema["maxLength"]
        if "pattern" in prop_schema:
            constraints["pattern"] = prop_schema["pattern"]
        if "format" in prop_schema:
            constraints["format"] = prop_schema["format"]

        # Number constraints
        if "minimum" in prop_schema:
            constraints["minimum"] = prop_schema["minimum"]
        if "maximum" in prop_schema:
            constraints["maximum"] = prop_schema["maximum"]
        if "exclusiveMinimum" in prop_schema:
            constraints["exclusiveMinimum"] = prop_schema["exclusiveMinimum"]
        if "exclusiveMaximum" in prop_schema:
            constraints["exclusiveMaximum"] = prop_schema["exclusiveMaximum"]

        # Enum
        if "enum" in prop_schema:
            constraints["enum"] = prop_schema["enum"]

        # Array constraints
        if "minItems" in prop_schema:
            constraints["minItems"] = prop_schema["minItems"]
        if "maxItems" in prop_schema:
            constraints["maxItems"] = prop_schema["maxItems"]
        if "uniqueItems" in prop_schema:
            constraints["uniqueItems"] = prop_schema["uniqueItems"]

        # Type
        if "type" in prop_schema:
            constraints["type"] = prop_schema["type"]

        return constraints

    def _compare_constraints(
        self,
        published: dict[str, dict],
        discovered: dict[str, dict],
    ) -> None:
        """Compare published vs discovered constraints.

        Args:
            published: Published constraints by field path
            discovered: Discovered constraints by field path
        """
        # Build name-based lookup for discovered constraints
        discovered_by_name: dict[str, list[dict]] = {}
        for path, constraints in discovered.items():
            name = constraints.get("name", path.split("/")[-1])
            if name not in discovered_by_name:
                discovered_by_name[name] = []
            discovered_by_name[name].append({"path": path, **constraints})

        # Compare each published field
        for pub_path, pub_constraints in published.items():
            pub_name = pub_constraints.get("name", pub_path.split("/")[-1])

            # Find matching discovered constraints
            disc_matches = discovered_by_name.get(pub_name, [])

            if not disc_matches:
                continue

            # Use the first match (could be smarter about matching)
            disc = disc_matches[0]

            # Compare each constraint type
            for constraint_type in [
                "minLength",
                "maxLength",
                "pattern",
                "format",
                "minimum",
                "maximum",
                "enum",
            ]:
                pub_value = pub_constraints.get(constraint_type)
                disc_value = disc.get(constraint_type)

                if disc_value is not None:
                    comparison = self._create_comparison(
                        field_name=pub_name,
                        field_path=pub_path,
                        constraint_type=constraint_type,
                        published_value=pub_value,
                        discovered_value=disc_value,
                    )

                    if comparison:
                        self.report.comparisons.append(comparison)
                        self.report.fields_with_diffs += 1

                        if pub_value is not None and self._is_tighter(
                            constraint_type,
                            pub_value,
                            disc_value,
                        ):
                            self.report.tighter_constraints.append(comparison)
                            self.report.tighter_constraints_found += 1
                        elif pub_value is None:
                            self.report.new_constraints.append(comparison)
                            self.report.new_constraints_found += 1

    def _create_comparison(
        self,
        field_name: str,
        field_path: str,
        constraint_type: str,
        published_value: Any,
        discovered_value: Any,
    ) -> ConstraintComparison | None:
        """Create a constraint comparison if there's a meaningful difference.

        Args:
            field_name: Name of the field
            field_path: Full path to the field
            constraint_type: Type of constraint
            published_value: Published value
            discovered_value: Discovered value

        Returns:
            ConstraintComparison or None if no meaningful difference
        """
        # Skip if values are equal
        if published_value == discovered_value:
            return None

        # Skip if published is None and discovered is default/empty
        if published_value is None and not discovered_value:
            return None

        recommendation = ""
        severity = "info"

        if constraint_type == "maxLength":
            if published_value and discovered_value < published_value:
                recommendation = (
                    f"Consider tightening maxLength from {published_value} to {discovered_value}"
                )
                severity = "warning"
            elif published_value is None:
                recommendation = f"Consider adding maxLength: {discovered_value}"

        elif constraint_type == "minLength":
            if published_value is None:
                recommendation = f"Consider adding minLength: {discovered_value}"

        elif constraint_type == "pattern":
            if published_value is None:
                recommendation = f"Consider adding pattern: {discovered_value}"

        elif constraint_type == "format":
            if published_value is None:
                recommendation = f"Consider adding format: {discovered_value}"

        elif constraint_type == "enum":
            if published_value is None:
                recommendation = f"Consider adding enum with {len(discovered_value)} values"

        return ConstraintComparison(
            field_name=field_name,
            field_path=field_path,
            constraint_type=constraint_type,
            published_value=published_value,
            discovered_value=discovered_value,
            recommendation=recommendation,
            severity=severity,
            confidence=0.9,
        )

    def _is_tighter(
        self,
        constraint_type: str,
        published_value: Any,
        discovered_value: Any,
    ) -> bool:
        """Check if discovered constraint is tighter than published.

        Args:
            constraint_type: Type of constraint
            published_value: Published value
            discovered_value: Discovered value

        Returns:
            True if discovered is tighter
        """
        if constraint_type == "maxLength":
            return discovered_value < published_value
        if constraint_type == "minLength":
            return discovered_value > published_value
        if constraint_type == "maximum":
            return discovered_value < published_value
        if constraint_type == "minimum":
            return discovered_value > published_value
        if constraint_type == "maxItems":
            return discovered_value < published_value
        if constraint_type == "minItems":
            return discovered_value > published_value

        return False

    def _find_undocumented_fields(
        self,
        published_schemas: dict,
        discovered_schemas: dict,
    ) -> None:
        """Find fields in discovered schemas that aren't in published specs.

        Args:
            published_schemas: Published schema definitions
            discovered_schemas: Discovered schema definitions
        """
        published_fields: set[str] = set()
        discovered_fields: set[str] = set()

        def collect_fields(schemas: dict, field_set: set) -> None:
            for schema in schemas.values():
                if not isinstance(schema, dict):
                    continue
                for prop_name in schema.get("properties", {}).keys():
                    field_set.add(prop_name)

        collect_fields(published_schemas, published_fields)
        collect_fields(discovered_schemas, discovered_fields)

        # Find fields only in discovered
        undocumented = discovered_fields - published_fields

        # Filter out common metadata fields that are expected
        expected_fields = {
            "tenant",
            "namespace",
            "name",
            "uid",
            "description",
            "disabled",
            "labels",
            "annotations",
            "creation_timestamp",
            "modification_timestamp",
            "creator",
            "system_metadata",
            "get_spec",
            "object_index",
        }

        undocumented = undocumented - expected_fields

        self.report.undocumented_fields = sorted(undocumented)
        self.report.undocumented_fields_found = len(undocumented)

    def to_dict(self) -> dict[str, Any]:
        """Convert constraint analysis report to dictionary."""
        return {
            "timestamp": self.generated_at,
            "summary": {
                "total_fields_analyzed": self.report.total_fields_analyzed,
                "fields_with_diffs": self.report.fields_with_diffs,
                "tighter_constraints_found": self.report.tighter_constraints_found,
                "new_constraints_found": self.report.new_constraints_found,
                "undocumented_fields_found": self.report.undocumented_fields_found,
            },
            "tighter_constraints": [
                {
                    "field": c.field_name,
                    "constraint": c.constraint_type,
                    "published": c.published_value,
                    "discovered": c.discovered_value,
                    "recommendation": c.recommendation,
                }
                for c in self.report.tighter_constraints[:100]
            ],
            "new_constraints": [
                {
                    "field": c.field_name,
                    "constraint": c.constraint_type,
                    "value": c.discovered_value,
                    "confidence": c.confidence,
                }
                for c in self.report.new_constraints[:100]
            ],
            "undocumented_fields": self.report.undocumented_fields[:50],
        }

    def to_markdown(self) -> str:
        """Convert constraint analysis report to markdown."""
        md = self.markdown_report_header()

        # Summary section
        md += self.markdown_section(
            "Summary",
            self._markdown_summary_table(),
            level=2,
        )

        # Server variables section
        sv_section = self.sv_helper.render_variable_constraints_section()
        if sv_section:
            md += sv_section

        # Tighter constraints section
        if self.report.tighter_constraints:
            headers = ["Field", "Constraint", "Published", "Discovered", "Recommendation"]
            rows = [
                [
                    c.field_name,
                    c.constraint_type,
                    str(c.published_value) if c.published_value is not None else "-",
                    str(c.discovered_value) if c.discovered_value is not None else "-",
                    c.recommendation,
                ]
                for c in self.report.tighter_constraints[:50]
            ]
            md += self.markdown_section(
                "Tighter Constraints Discovered",
                self.markdown_table(headers, rows),
                level=2,
            )

        # New constraints section
        if self.report.new_constraints:
            headers = ["Field", "Constraint", "Value", "Confidence"]
            rows = [
                [
                    c.field_name,
                    c.constraint_type,
                    self._format_constraint_value(c.discovered_value),
                    f"{c.confidence * 100:.0f}%",
                ]
                for c in self.report.new_constraints[:50]
            ]
            md += self.markdown_section(
                "New Constraints Found",
                self.markdown_table(headers, rows),
                level=2,
            )

        # Undocumented fields section
        if self.report.undocumented_fields:
            fields_content = "\n".join(
                f"- `{field}`" for field in self.report.undocumented_fields[:30]
            )
            if len(self.report.undocumented_fields) > 30:
                remaining = len(self.report.undocumented_fields) - 30
                fields_content += f"\n- ... and {remaining} more"
            md += self.markdown_section(
                "Undocumented Fields Discovered",
                fields_content,
                level=2,
            )

        return md

    def _markdown_summary_table(self) -> str:
        """Create markdown summary table."""
        headers = ["Metric", "Value"]
        rows = [
            ["Total Fields Analyzed", str(self.report.total_fields_analyzed)],
            ["Fields with Differences", str(self.report.fields_with_diffs)],
            ["Tighter Constraints Found", str(self.report.tighter_constraints_found)],
            ["New Constraints Found", str(self.report.new_constraints_found)],
            ["Undocumented Fields", str(self.report.undocumented_fields_found)],
        ]
        return self.markdown_table(headers, rows)

    def _format_constraint_value(self, value: Any) -> str:
        """Format constraint value for display."""
        if isinstance(value, list):
            return f"[{len(value)} values]"
        if isinstance(value, str) and len(value) > 40:
            return value[:40] + "..."
        return str(value)

    def generate_markdown_report(self, output_path: Path | str | None = None) -> Path:
        """Generate a markdown report from the analysis.

        Args:
            output_path: Path for the output file (uses PathConfig if not provided)

        Returns:
            Path to the generated report
        """
        if output_path is None:
            output_path = self.path_config.constraint_analysis

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self.to_markdown())
        return output_path

    def generate_json_report(self, output_path: Path | str | None = None) -> Path:
        """Generate a JSON report from the analysis.

        Args:
            output_path: Path for the output file (uses PathConfig if not provided)

        Returns:
            Path to the generated report
        """
        if output_path is None:
            output_path = self.path_config.constraint_analysis_json

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("w") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)
            f.write("\n")

        return output_path

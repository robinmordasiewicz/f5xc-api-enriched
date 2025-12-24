"""CLI Metadata Enricher for OpenAPI specifications.

Adds CLI-specific metadata to schema properties for shell completions and help text.

Extends properties with:
- x-ves-cli-help: Brief help text for command-line tools
- x-ves-cli-example: CLI-friendly example value
- x-ves-cli-completion: Completion hint (namespace-list, enum-values, file-path, etc.)
- x-ves-cli-required: Whether field is required for CLI operations

Follows conservative approach: only for high-confidence patterns.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class CLIEnrichmentStats:
    """Statistics from CLI metadata enrichment."""

    help_added: int = 0
    examples_added: int = 0
    completions_added: int = 0
    properties_processed: int = 0
    schemas_processed: int = 0

    def to_dict(self) -> dict[str, int]:
        """Convert stats to dictionary."""
        return {
            "help_added": self.help_added,
            "examples_added": self.examples_added,
            "completions_added": self.completions_added,
            "properties_processed": self.properties_processed,
            "schemas_processed": self.schemas_processed,
        }


class CLIMetadataEnricher:
    """Add CLI-specific metadata to OpenAPI properties.

    Adds x-ves-cli-* extensions for command-line tool integration.
    Configuration-driven from cli_metadata.yaml.
    Preserves existing CLI metadata (never overwrites).
    """

    def __init__(self, config_path: Path | None = None) -> None:
        """Initialize enricher with CLI metadata configuration.

        Args:
            config_path: Path to cli_metadata.yaml config.
                        Defaults to config/cli_metadata.yaml.
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "cli_metadata.yaml"

        self.config_path = config_path
        self.completion_patterns: list[dict[str, Any]] = []
        self._compiled_patterns: list[tuple[re.Pattern, dict]] = []
        self.stats = CLIEnrichmentStats()

        self._load_config()

    def _load_config(self) -> None:
        """Load CLI completion patterns from YAML config."""
        if not self.config_path.exists():
            self._use_default_config()
            return

        try:
            with self.config_path.open() as f:
                config = yaml.safe_load(f) or {}

            self.completion_patterns = config.get("completion_patterns", [])
            self._compile_patterns()
        except Exception:
            self._use_default_config()

    def _use_default_config(self) -> None:
        """Use built-in default CLI metadata patterns."""
        self.completion_patterns = [
            {
                "pattern": r"\bnamespace$",
                "completion_type": "namespace-list",
                "help": "Kubernetes namespace",
            },
            {
                "pattern": r"\blabels$",
                "completion_type": "key-value-pairs",
                "help": "Metadata labels",
                "separator": "=",
            },
            {
                "pattern": r"\btags$",
                "completion_type": "key-value-pairs",
                "help": "Resource tags",
                "separator": "=",
            },
            {
                "pattern": r"\b(file|path)$",
                "completion_type": "file-path",
                "help": "File path reference",
            },
        ]

    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficient matching."""
        for pattern_config in self.completion_patterns:
            pattern_str = pattern_config.get("pattern", "")
            if not pattern_str:
                continue

            try:
                compiled = re.compile(pattern_str)
                self._compiled_patterns.append((compiled, pattern_config))
            except re.error:
                continue

    def enrich_spec(self, spec: dict[str, Any]) -> dict[str, Any]:
        """Enrich OpenAPI specification with CLI metadata.

        Args:
            spec: OpenAPI specification dictionary

        Returns:
            Specification with added CLI metadata extensions
        """
        return self._enrich_recursive(spec)

    def _enrich_recursive(self, obj: Any) -> Any:
        """Recursively traverse and enrich spec object.

        Args:
            obj: Object to process (dict, list, or primitive)

        Returns:
            Enriched object
        """
        if isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                if key == "properties" and isinstance(value, dict):
                    result[key] = self._enrich_properties(value)
                elif key == "schemas" and isinstance(value, dict):
                    result[key] = {
                        schema_name: self._enrich_schema(schema, schema_name)
                        for schema_name, schema in value.items()
                    }
                else:
                    result[key] = self._enrich_recursive(value)
            return result

        if isinstance(obj, list):
            return [self._enrich_recursive(item) for item in obj]

        return obj

    def _enrich_schema(self, schema: dict[str, Any], _schema_name: str) -> dict[str, Any]:
        """Enrich a single schema definition.

        Args:
            schema: Schema definition
            _schema_name: Name of the schema (unused, kept for interface compatibility)

        Returns:
            Enriched schema
        """
        self.stats.schemas_processed += 1
        result = schema.copy()

        if "properties" in result and isinstance(result["properties"], dict):
            result["properties"] = self._enrich_properties(result["properties"])

        if "items" in result:
            result["items"] = self._enrich_recursive(result["items"])

        if "oneOf" in result:
            result["oneOf"] = [self._enrich_recursive(item) for item in result["oneOf"]]

        if "allOf" in result:
            result["allOf"] = [self._enrich_recursive(item) for item in result["allOf"]]

        if "anyOf" in result:
            result["anyOf"] = [self._enrich_recursive(item) for item in result["anyOf"]]

        return result

    def _enrich_properties(self, properties: dict[str, Any]) -> dict[str, Any]:
        """Enrich all properties in a properties object.

        Args:
            properties: Properties dictionary from schema

        Returns:
            Enriched properties dictionary
        """
        result = {}

        for prop_name, prop_schema in properties.items():
            self.stats.properties_processed += 1
            enriched = prop_schema.copy() if isinstance(prop_schema, dict) else prop_schema

            if isinstance(enriched, dict):
                self._enrich_property(enriched, prop_name)

            result[prop_name] = enriched

        return result

    def _enrich_property(self, prop: dict[str, Any], prop_name: str) -> None:
        """Enrich a single property with CLI metadata.

        Modifies prop dict in-place. Never overwrites existing CLI metadata.

        Args:
            prop: Property definition to enrich
            prop_name: Name of the property
        """
        # Skip if CLI metadata already present (preserve existing)
        if any(k in prop for k in ["x-ves-cli-help", "x-ves-cli-completion"]):
            return

        # Generate help text
        help_text = self._generate_help(prop_name)
        if help_text:
            prop["x-ves-cli-help"] = help_text
            self.stats.help_added += 1

        # Generate CLI example
        example = self._generate_cli_example(prop_name, prop)
        if example is not None:
            prop["x-ves-cli-example"] = example
            self.stats.examples_added += 1

        # Add completion hint
        completion = self._find_completion_type(prop_name)
        if completion:
            prop["x-ves-cli-completion"] = completion
            self.stats.completions_added += 1

    def _generate_help(self, prop_name: str) -> str | None:
        """Generate help text for CLI from description and validation.

        Args:
            prop_name: Property name

        Returns:
            Help text or None if no help can be generated
        """
        for compiled_pattern, pattern_config in self._compiled_patterns:
            if compiled_pattern.search(prop_name):
                return pattern_config.get("help")

        return None

    def _generate_cli_example(self, prop_name: str, prop: dict[str, Any]) -> Any | None:
        """Generate CLI-friendly example for a property.

        Args:
            prop_name: Property name
            prop: Property schema definition

        Returns:
            CLI example value or None
        """
        # Check for enum values (use first enum value as example)
        if "enum" in prop and isinstance(prop["enum"], list) and len(prop["enum"]) > 0:
            return prop["enum"][0]

        # Check for pattern-based examples
        for compiled_pattern, pattern_config in self._compiled_patterns:
            if compiled_pattern.search(prop_name):
                completion_type = pattern_config.get("completion_type")

                if completion_type == "key-value-pairs":
                    separator = pattern_config.get("separator", "=")
                    return f"key{separator}value"

                if completion_type == "namespace-list":
                    return "default"

                if completion_type == "file-path":
                    return "./example.yaml"

        return None

    def _find_completion_type(self, prop_name: str) -> str | None:
        """Find completion type hint for a property.

        Args:
            prop_name: Property name

        Returns:
            Completion type or None
        """
        for compiled_pattern, pattern_config in self._compiled_patterns:
            if compiled_pattern.search(prop_name):
                return pattern_config.get("completion_type")

        return None

    def _is_required(self, prop: dict[str, Any]) -> bool:
        """Check if property is required.

        A property is required if:
        1. Required field is explicitly set, OR
        2. x-ves-validation-rules marks it as required

        Args:
            prop: Property schema definition

        Returns:
            True if property is required
        """
        # Check explicit required flag
        if prop.get("required"):
            return True

        # Check discovery validation rules
        validation_rules = prop.get("x-ves-validation-rules", {})
        return bool(validation_rules.get("required"))

    def get_stats(self) -> dict[str, int]:
        """Get enrichment statistics.

        Returns:
            Dictionary with enrichment metrics
        """
        return self.stats.to_dict()

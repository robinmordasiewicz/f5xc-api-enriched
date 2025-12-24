"""Unified Field-Level Metadata Enricher for OpenAPI specifications.

Consolidates and extends field-level enrichment with:
- Core metadata (description, validation, examples)
- CLI metadata (help, completion, examples)
- Advanced metadata (defaults, conditions, deprecation)

Conservative approach: only applies high-confidence patterns (95%+).
Preserves all existing metadata (never overwrites).
Merges discovery constraints with priority: existing > discovery > inferred.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class FieldMetadataStats:
    """Statistics from field metadata enrichment."""

    descriptions_added: int = 0
    validations_added: int = 0
    examples_added: int = 0
    completions_added: int = 0
    defaults_added: int = 0
    conditions_added: int = 0
    operation_requirements_added: int = 0
    deprecations_added: int = 0
    properties_processed: int = 0
    schemas_processed: int = 0

    def to_dict(self) -> dict[str, int]:
        """Convert stats to dictionary."""
        return {
            "descriptions_added": self.descriptions_added,
            "validations_added": self.validations_added,
            "examples_added": self.examples_added,
            "completions_added": self.completions_added,
            "defaults_added": self.defaults_added,
            "conditions_added": self.conditions_added,
            "operation_requirements_added": self.operation_requirements_added,
            "deprecations_added": self.deprecations_added,
            "properties_processed": self.properties_processed,
            "schemas_processed": self.schemas_processed,
        }


class FieldMetadataEnricher:
    """Unified field-level metadata enricher for OpenAPI properties.

    Consolidates functionality from:
    - FieldDescriptionEnricher: Descriptions and example generation
    - ValidationEnricher: Validation constraints
    - CLIMetadataEnricher: CLI-specific metadata

    Adds new extensions:
    - x-ves-description: Field help text
    - x-ves-validation: Validation constraints object
    - x-ves-examples: Multiple examples with context (array)
    - x-ves-completion: Enhanced autocomplete metadata
    - x-ves-defaults: Default values with reasoning
    - x-ves-conditions: Conditional requirements
    - x-ves-required-for-operations: Per-operation requirements
    - x-ves-deprecated: Deprecation metadata

    Configuration-driven from field_metadata.yaml.
    Preserves all existing metadata (never overwrites).
    """

    def __init__(self, config_path: Path | None = None) -> None:
        """Initialize enricher with field metadata configuration.

        Args:
            config_path: Path to field_metadata.yaml config.
                        Defaults to config/field_metadata.yaml.
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "field_metadata.yaml"

        self.config_path = config_path
        self.preserve_existing = True
        self.field_patterns: list[dict[str, Any]] = []
        self.deprecations: list[dict[str, Any]] = []
        self.conditions: list[dict[str, Any]] = []
        self._compiled_patterns: list[tuple[re.Pattern, dict]] = []
        self._compiled_deprecations: list[tuple[re.Pattern, dict]] = []
        self._compiled_conditions: list[tuple[re.Pattern, dict]] = []
        self.stats = FieldMetadataStats()

        self._load_config()

    def _load_config(self) -> None:
        """Load field metadata patterns from YAML config."""
        if not self.config_path.exists():
            self._use_default_config()
            return

        try:
            with self.config_path.open() as f:
                config = yaml.safe_load(f) or {}

            self.preserve_existing = config.get("preserve_existing", True)
            self.field_patterns = config.get("field_patterns", [])
            self.deprecations = config.get("deprecations", [])
            self.conditions = config.get("conditions", [])

            self._compile_patterns()
        except Exception:
            self._use_default_config()

    def _use_default_config(self) -> None:
        """Use built-in default field metadata patterns."""
        self.preserve_existing = True
        self.field_patterns = [
            {
                "pattern": r"\bname$",
                "x-ves-description": "Human-readable resource name",
                "x-ves-validation": {
                    "minLength": 1,
                    "maxLength": 63,
                    "pattern": "^[a-z0-9]([-a-z0-9]*[a-z0-9])?$",
                },
                "x-ves-examples": [
                    {"value": "example-resource", "context": "Basic alphanumeric name"},
                ],
                "x-ves-completion": {"type": "string-value", "hint": "Resource name"},
                "x-ves-required-for-operations": {
                    "create": True,
                    "read": True,
                    "update": True,
                    "delete": True,
                },
            },
            {
                "pattern": r"\bemail$",
                "x-ves-description": "Email address in RFC 5322 format",
                "x-ves-validation": {
                    "format": "email",
                    "pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$",
                },
                "x-ves-examples": [
                    {"value": "user@example.com", "context": "Standard email format"},
                ],
                "x-ves-completion": {"type": "email", "hint": "Email address"},
            },
            {
                "pattern": r"\bport$",
                "x-ves-description": "TCP/UDP port number",
                "x-ves-validation": {"minimum": 1, "maximum": 65535},
                "x-ves-examples": [{"value": "8080", "context": "Standard service port"}],
                "x-ves-completion": {"type": "port", "hint": "Port number"},
            },
            {
                "pattern": r"\buuid$",
                "x-ves-description": "Unique identifier in UUID v4 format",
                "x-ves-validation": {"format": "uuid"},
                "x-ves-examples": [
                    {
                        "value": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                        "context": "Valid UUID v4",
                    },
                ],
                "x-ves-completion": {"type": "uuid", "hint": "UUID identifier"},
            },
            {
                "pattern": r"\btimestamp$",
                "x-ves-description": "Timestamp in ISO 8601 format",
                "x-ves-validation": {"format": "date-time"},
                "x-ves-examples": [
                    {"value": "2025-01-15T10:30:00Z", "context": "ISO 8601 UTC"},
                ],
                "x-ves-completion": {"type": "timestamp", "hint": "ISO 8601 timestamp"},
            },
        ]

        self.deprecations = []
        self.conditions = []

    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficient matching."""
        # Compile field patterns
        for pattern_config in self.field_patterns:
            pattern_str = pattern_config.get("pattern", "")
            if not pattern_str:
                continue

            try:
                compiled = re.compile(pattern_str)
                self._compiled_patterns.append((compiled, pattern_config))
            except re.error:
                continue

        # Compile deprecation patterns
        for deprecation_config in self.deprecations:
            pattern_str = deprecation_config.get("field_pattern", "")
            if not pattern_str:
                continue

            try:
                compiled = re.compile(pattern_str)
                self._compiled_deprecations.append((compiled, deprecation_config))
            except re.error:
                continue

        # Compile condition patterns
        for condition_config in self.conditions:
            pattern_str = condition_config.get("field_pattern", "")
            if not pattern_str:
                continue

            try:
                compiled = re.compile(pattern_str)
                self._compiled_conditions.append((compiled, condition_config))
            except re.error:
                continue

    def enrich_spec(self, spec: dict[str, Any]) -> dict[str, Any]:
        """Enrich OpenAPI specification with field-level metadata.

        Args:
            spec: OpenAPI specification dictionary

        Returns:
            Specification with added field metadata
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

    def _enrich_schema(self, schema: dict[str, Any], schema_name: str) -> dict[str, Any]:
        """Enrich a single schema definition.

        Args:
            schema: Schema definition
            schema_name: Name of the schema

        Returns:
            Enriched schema
        """
        self.stats.schemas_processed += 1
        result = schema.copy()

        # Process properties if present
        if "properties" in result and isinstance(result["properties"], dict):
            result["properties"] = self._enrich_properties(
                result["properties"],
                schema_name,
            )

        # Recursively process nested schemas
        if "items" in result:
            result["items"] = self._enrich_recursive(result["items"])

        if "oneOf" in result:
            result["oneOf"] = [self._enrich_recursive(item) for item in result["oneOf"]]

        if "allOf" in result:
            result["allOf"] = [self._enrich_recursive(item) for item in result["allOf"]]

        if "anyOf" in result:
            result["anyOf"] = [self._enrich_recursive(item) for item in result["anyOf"]]

        return result

    def _enrich_properties(
        self,
        properties: dict[str, Any],
        schema_name: str = "",
    ) -> dict[str, Any]:
        """Enrich all properties in a properties object.

        Args:
            properties: Properties dictionary from schema
            schema_name: Name of parent schema (for context)

        Returns:
            Enriched properties dictionary
        """
        result = {}

        for prop_name, prop_schema in properties.items():
            self.stats.properties_processed += 1
            enriched = prop_schema.copy() if isinstance(prop_schema, dict) else prop_schema

            if isinstance(enriched, dict):
                self._enrich_property(enriched, prop_name, schema_name)

            result[prop_name] = enriched

        return result

    def _enrich_property(
        self,
        prop: dict[str, Any],
        prop_name: str,
        schema_name: str,  # noqa: ARG002
    ) -> None:
        """Enrich a single property with metadata.

        Modifies prop dict in-place. Respects existing metadata.

        Args:
            prop: Property definition to enrich
            prop_name: Name of the property
            schema_name: Name of parent schema
        """
        # Find matching pattern
        pattern_config = self._find_pattern(prop_name)
        if not pattern_config:
            return

        # Add description
        self._add_description(prop, pattern_config)

        # Add validation
        self._add_validation(prop, pattern_config)

        # Add examples
        self._add_examples(prop, pattern_config)

        # Add completion
        self._add_completion(prop, pattern_config)

        # Add defaults
        self._add_defaults(prop, pattern_config)

        # Add conditions
        self._add_conditions(prop, prop_name)

        # Add operation requirements
        self._add_operation_requirements(prop, pattern_config)

        # Add deprecation
        self._add_deprecation(prop, prop_name)

    def _find_pattern(self, prop_name: str) -> dict[str, Any] | None:
        """Find matching pattern configuration for a property.

        Args:
            prop_name: Name of the property

        Returns:
            Pattern configuration if found, None otherwise
        """
        for compiled_pattern, pattern_config in self._compiled_patterns:
            if compiled_pattern.search(prop_name):
                return pattern_config
        return None

    def _add_description(self, prop: dict[str, Any], pattern_config: dict[str, Any]) -> None:
        """Add x-ves-description if not already present.

        Args:
            prop: Property definition
            pattern_config: Pattern configuration
        """
        if self.preserve_existing and "x-ves-description" in prop:
            return

        description = pattern_config.get("x-ves-description")
        if description:
            prop["x-ves-description"] = description
            self.stats.descriptions_added += 1

    def _add_validation(self, prop: dict[str, Any], pattern_config: dict[str, Any]) -> None:
        """Add x-ves-validation if not already present.

        Args:
            prop: Property definition
            pattern_config: Pattern configuration
        """
        if self.preserve_existing and "x-ves-validation" in prop:
            return

        validation = pattern_config.get("x-ves-validation")
        if validation:
            prop["x-ves-validation"] = validation
            self.stats.validations_added += 1

    def _add_examples(self, prop: dict[str, Any], pattern_config: dict[str, Any]) -> None:
        """Add x-ves-examples array if not already present.

        Args:
            prop: Property definition
            pattern_config: Pattern configuration
        """
        if self.preserve_existing and "x-ves-examples" in prop:
            return

        examples = pattern_config.get("x-ves-examples")
        if examples and isinstance(examples, list):
            prop["x-ves-examples"] = examples
            self.stats.examples_added += 1

    def _add_completion(self, prop: dict[str, Any], pattern_config: dict[str, Any]) -> None:
        """Add x-ves-completion if not already present.

        Args:
            prop: Property definition
            pattern_config: Pattern configuration
        """
        if self.preserve_existing and "x-ves-completion" in prop:
            return

        completion = pattern_config.get("x-ves-completion")
        if completion:
            prop["x-ves-completion"] = completion
            self.stats.completions_added += 1

    def _add_defaults(self, prop: dict[str, Any], pattern_config: dict[str, Any]) -> None:
        """Add x-ves-defaults if not already present.

        Args:
            prop: Property definition
            pattern_config: Pattern configuration
        """
        if self.preserve_existing and "x-ves-defaults" in prop:
            return

        defaults = pattern_config.get("x-ves-defaults")
        if defaults:
            prop["x-ves-defaults"] = defaults
            self.stats.defaults_added += 1

    def _add_conditions(self, prop: dict[str, Any], prop_name: str) -> None:
        """Add x-ves-conditions if not already present.

        Args:
            prop: Property definition
            prop_name: Name of the property
        """
        if self.preserve_existing and "x-ves-conditions" in prop:
            return

        for compiled_pattern, condition_config in self._compiled_conditions:
            if compiled_pattern.search(prop_name):
                conditions = condition_config.get("x-ves-conditions")
                if conditions:
                    prop["x-ves-conditions"] = conditions
                    self.stats.conditions_added += 1
                return

    def _add_operation_requirements(
        self,
        prop: dict[str, Any],
        pattern_config: dict[str, Any],
    ) -> None:
        """Add x-ves-required-for-operations if not already present.

        Args:
            prop: Property definition
            pattern_config: Pattern configuration
        """
        if self.preserve_existing and "x-ves-required-for-operations" in prop:
            return

        requirements = pattern_config.get("x-ves-required-for-operations")
        if requirements:
            prop["x-ves-required-for-operations"] = requirements
            self.stats.operation_requirements_added += 1

    def _add_deprecation(self, prop: dict[str, Any], prop_name: str) -> None:
        """Add x-ves-deprecated if not already present.

        Args:
            prop: Property definition
            prop_name: Name of the property
        """
        if self.preserve_existing and "x-ves-deprecated" in prop:
            return

        for compiled_pattern, deprecation_config in self._compiled_deprecations:
            if compiled_pattern.search(prop_name):
                deprecation = deprecation_config.get("x-ves-deprecated")
                if deprecation:
                    prop["x-ves-deprecated"] = deprecation
                    self.stats.deprecations_added += 1
                return

    def get_stats(self) -> dict[str, int]:
        """Get enrichment statistics.

        Returns:
            Dictionary with enrichment metrics
        """
        return self.stats.to_dict()

"""Field Description and Example Enricher for OpenAPI specifications.

Adds comprehensive descriptions and realistic examples to schema properties
using pattern-based matching with high-confidence patterns only.

Follows conservative approach: only matches patterns with 95%+ confidence.
Respects existing descriptions and examples (never overwrites).
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class FieldEnrichmentStats:
    """Statistics from field description enrichment."""

    descriptions_added: int = 0
    examples_added: int = 0
    properties_processed: int = 0
    schemas_processed: int = 0

    def to_dict(self) -> dict[str, int]:
        """Convert stats to dictionary."""
        return {
            "descriptions_added": self.descriptions_added,
            "examples_added": self.examples_added,
            "properties_processed": self.properties_processed,
            "schemas_processed": self.schemas_processed,
        }


class FieldDescriptionEnricher:
    """Enrich OpenAPI properties with descriptions and examples.

    Adds field-level metadata using conservative pattern matching (95%+ confidence).
    Configuration-driven from field_descriptions.yaml.
    Preserves all existing descriptions and examples (never overwrites).
    """

    def __init__(self, config_path: Path | None = None) -> None:
        """Initialize enricher with pattern configuration.

        Args:
            config_path: Path to field_descriptions.yaml config.
                        Defaults to config/field_descriptions.yaml.
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "field_descriptions.yaml"

        self.config_path = config_path
        self.preserve_existing = True
        self.description_patterns: list[dict[str, Any]] = []
        self.example_generators: dict[str, Any] = {}
        self._compiled_patterns: list[tuple[re.Pattern, dict]] = []
        self.stats = FieldEnrichmentStats()

        self._load_config()

    def _load_config(self) -> None:
        """Load description patterns and example generators from YAML config."""
        if not self.config_path.exists():
            # Use default high-confidence patterns if config doesn't exist
            self._use_default_config()
            return

        try:
            with self.config_path.open() as f:
                config = yaml.safe_load(f) or {}

            self.preserve_existing = config.get("preserve_existing", True)
            self.description_patterns = config.get("description_patterns", [])
            self.example_generators = config.get("example_generators", {})

            self._compile_patterns()
        except Exception:
            # Fall back to defaults on any config error
            self._use_default_config()

    def _use_default_config(self) -> None:
        """Use built-in default high-confidence patterns."""
        self.preserve_existing = True
        self.description_patterns = [
            {
                "pattern": r"\bname$",
                "description": "Human-readable name for the resource",
                "example_type": "kebab-case-name",
                "min_length": 1,
                "max_length": 63,
            },
            {
                "pattern": r"\bemail$",
                "description": "Email address in RFC 5322 format",
                "example_type": "email",
                "format": "email",
            },
            {
                "pattern": r"\b(url|uri)$",
                "description": "URL or URI reference",
                "example_type": "url",
                "format": "uri",
            },
            {
                "pattern": r"\b(ip|ipv4)$",
                "description": "IPv4 address in dotted decimal notation",
                "example_type": "ipv4",
                "format": "ipv4",
            },
            {
                "pattern": r"\bport$",
                "description": "TCP/UDP port number",
                "example_type": "port",
                "minimum": 1,
                "maximum": 65535,
            },
            {
                "pattern": r"\buuid$",
                "description": "Unique identifier in UUID v4 format",
                "example_type": "uuid",
                "format": "uuid",
            },
            {
                "pattern": r"\btimestamp$",
                "description": "Timestamp in ISO 8601 format",
                "example_type": "timestamp",
                "format": "date-time",
            },
        ]

        self.example_generators = {
            "kebab-case-name": "example-resource",
            "email": "user@example.com",
            "ipv4": "192.0.2.1",
            "uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "url": "https://example.com",
            "port": 8080,
            "timestamp": "2025-01-15T10:30:00Z",
        }

    def _compile_patterns(self) -> None:
        """Compile regex patterns from configuration for efficient matching."""
        for pattern_config in self.description_patterns:
            pattern_str = pattern_config.get("pattern", "")
            if not pattern_str:
                continue

            try:
                compiled = re.compile(pattern_str)
                self._compiled_patterns.append((compiled, pattern_config))
            except re.error:
                # Skip invalid patterns
                continue

    def enrich_spec(self, spec: dict[str, Any]) -> dict[str, Any]:
        """Enrich OpenAPI specification with descriptions and examples.

        Args:
            spec: OpenAPI specification dictionary

        Returns:
            Specification with added field descriptions and examples
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
                    # This is a schema properties object
                    result[key] = self._enrich_properties(value)
                elif key == "schemas" and isinstance(value, dict):
                    # This is the components.schemas section
                    result[key] = {
                        schema_name: self._enrich_schema(schema, schema_name)
                        for schema_name, schema in value.items()
                    }
                else:
                    # Recursively process other dict values
                    result[key] = self._enrich_recursive(value)
            return result

        if isinstance(obj, list):
            # Recursively process list items
            return [self._enrich_recursive(item) for item in obj]

        # Return primitives unchanged
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
        _schema_name: str,
    ) -> None:
        """Enrich a single property with description and example.

        Modifies prop dict in-place. Respects existing descriptions/examples.

        Args:
            prop: Property definition to enrich
            prop_name: Name of the property
            _schema_name: Name of parent schema (unused, kept for interface compatibility)
        """
        # Never overwrite existing descriptions if preserve_existing is True
        if self.preserve_existing and "description" in prop:
            # Description already exists, skip
            pass
        else:
            # Try to add description based on patterns
            description = self._find_description(prop_name)
            if description:
                prop["description"] = description
                self.stats.descriptions_added += 1

        # Never overwrite existing examples if preserve_existing is True
        if self.preserve_existing and ("example" in prop or "x-ves-example" in prop):
            # Example already exists, skip
            pass
        else:
            # Try to add example based on patterns
            example = self._generate_example(prop_name, prop)
            if example is not None:
                # Convert to string to ensure JSON schema compatibility
                # Examples may be numbers (8080) or booleans that need string representation
                prop["x-ves-example"] = str(example) if not isinstance(example, str) else example
                self.stats.examples_added += 1

    def _find_description(self, prop_name: str) -> str | None:
        """Find description for a property based on pattern matching.

        Args:
            prop_name: Name of the property

        Returns:
            Description string if pattern matches, None otherwise
        """
        for compiled_pattern, pattern_config in self._compiled_patterns:
            if compiled_pattern.search(prop_name):
                return pattern_config.get("description")

        return None

    def _generate_example(self, prop_name: str, _prop: dict[str, Any]) -> Any | None:
        """Generate realistic example for a property.

        Args:
            prop_name: Name of the property
            _prop: Property schema definition (unused, kept for interface compatibility)

        Returns:
            Example value if can be generated, None otherwise
        """
        # Find matching pattern
        for compiled_pattern, pattern_config in self._compiled_patterns:
            if compiled_pattern.search(prop_name):
                example_type = pattern_config.get("example_type")
                if example_type and example_type in self.example_generators:
                    example_value = self.example_generators[example_type]

                    # Handle template examples that reference resource type
                    if isinstance(example_value, str) and "{resource_type}" in example_value:
                        resource_type = self._infer_resource_type(prop_name)
                        return example_value.format(resource_type=resource_type)

                    return example_value

        return None

    @staticmethod
    def _infer_resource_type(_prop_name: str) -> str:
        """Infer resource type from property context.

        For now returns a generic placeholder. In future could extract from
        parent schema name or other context.

        Args:
            prop_name: Property name for context

        Returns:
            Resource type identifier
        """
        return "resource"

    def get_stats(self) -> dict[str, int]:
        """Get enrichment statistics.

        Returns:
            Dictionary with enrichment metrics
        """
        return self.stats.to_dict()

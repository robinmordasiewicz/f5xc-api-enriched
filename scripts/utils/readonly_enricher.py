"""ReadOnly Field Enricher for OpenAPI specifications.

Adds `readOnly: true` to API-computed fields following the OpenAPI 3.0 standard.
These fields are server-generated and should not be set by clients.

Downstream tooling (e.g., xcsh CLI) can use this to automatically exclude
these fields from create/update request payloads.
"""

import contextlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ReadOnlyStats:
    """Statistics from readOnly field enrichment."""

    metadata_fields_marked: int = 0
    object_ref_fields_marked: int = 0
    schemas_processed: int = 0
    schemas_matched: int = 0
    metadata_schemas_matched: int = 0
    object_ref_schemas_matched: int = 0
    fields_by_name: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert stats to dictionary."""
        return {
            "metadata_fields_marked": self.metadata_fields_marked,
            "object_ref_fields_marked": self.object_ref_fields_marked,
            "total_fields_marked": self.metadata_fields_marked + self.object_ref_fields_marked,
            "schemas_processed": self.schemas_processed,
            "schemas_matched": self.schemas_matched,
            "metadata_schemas_matched": self.metadata_schemas_matched,
            "object_ref_schemas_matched": self.object_ref_schemas_matched,
            "fields_by_name": self.fields_by_name,
        }


class ReadOnlyEnricher:
    """Enricher that adds readOnly annotations to API-computed fields.

    Identifies fields that are computed by the F5 XC API server and marks them
    with `readOnly: true` following OpenAPI 3.0 standard.

    Target field categories:
    1. Metadata fields (tenant, uid, kind, timestamps, creator info, etc.)
    2. ObjectRef fields (auto-populated reference fields)

    Configuration-driven from readonly_fields.yaml.
    Preserves existing readOnly values (never overwrites).
    """

    def __init__(self, config_path: Path | None = None) -> None:
        """Initialize enricher with readOnly fields configuration.

        Args:
            config_path: Path to readonly_fields.yaml config.
                        Defaults to config/readonly_fields.yaml.
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "readonly_fields.yaml"

        self.config_path = config_path
        self.metadata_fields: dict[str, dict[str, str]] = {}
        self.object_ref_fields: dict[str, dict[str, str]] = {}
        self.metadata_patterns: list[re.Pattern] = []
        self.object_ref_patterns: list[re.Pattern] = []
        self.stats = ReadOnlyStats()

        self._load_config()

    def _load_config(self) -> None:
        """Load readOnly field configuration from YAML config."""
        if not self.config_path.exists():
            self._use_default_config()
            return

        try:
            with self.config_path.open() as f:
                config = yaml.safe_load(f) or {}

            self.metadata_fields = config.get("metadata_fields", {})
            self.object_ref_fields = config.get("object_ref_fields", {})

            # Compile schema name patterns
            self.metadata_patterns = self._compile_patterns(
                config.get("metadata_patterns", []),
            )
            self.object_ref_patterns = self._compile_patterns(
                config.get("object_ref_patterns", []),
            )

        except Exception:
            self._use_default_config()

    def _compile_patterns(self, pattern_strings: list[str]) -> list[re.Pattern]:
        """Compile a list of regex pattern strings.

        Args:
            pattern_strings: List of regex pattern strings

        Returns:
            List of compiled regex patterns (invalid patterns are skipped)
        """
        compiled: list[re.Pattern] = []
        for pattern_str in pattern_strings:
            with contextlib.suppress(re.error):
                compiled.append(re.compile(pattern_str))
        return compiled

    def _use_default_config(self) -> None:
        """Use built-in default readOnly field configuration."""
        self.metadata_fields = {
            "tenant": {"description": "Set by API from authentication context"},
            "uid": {"description": "Generated unique identifier by API"},
            "kind": {"description": "Set by API based on object type"},
            "creation_timestamp": {"description": "Set by server on object creation"},
            "modification_timestamp": {"description": "Updated by server on each modification"},
            "creator_id": {"description": "Set by API from authentication context"},
            "creator_class": {"description": "Set by API from authentication context"},
            "object_index": {"description": "Internal index maintained by API"},
            "owner_view": {"description": "Set by API based on permissions"},
        }

        self.object_ref_fields = {
            "tenant": {"description": "Auto-populated for object references from context"},
            "uid": {"description": "Auto-populated for object references by API"},
            "kind": {"description": "Auto-populated for object references based on target type"},
        }

        self.metadata_patterns = [
            re.compile(r"ObjectMetaType"),
            re.compile(r".*MetadataType$"),
            re.compile(r"SystemMetadata"),
        ]

        self.object_ref_patterns = [
            re.compile(r"ObjectRefType"),
            re.compile(r".*ObjectRef$"),
            re.compile(r".*Ref$"),
        ]

    def enrich_spec(self, spec: dict[str, Any]) -> dict[str, Any]:
        """Enrich OpenAPI specification with readOnly annotations.

        Args:
            spec: OpenAPI specification dictionary

        Returns:
            Specification with readOnly annotations added to computed fields
        """
        # Reset stats for this enrichment run
        self.stats = ReadOnlyStats()

        # Process schemas in components
        if "components" in spec and "schemas" in spec["components"]:
            spec["components"]["schemas"] = self._process_schemas(
                spec["components"]["schemas"],
            )

        return spec

    def _process_schemas(self, schemas: dict[str, Any]) -> dict[str, Any]:
        """Process all schemas and add readOnly where appropriate.

        Args:
            schemas: Dictionary of schema definitions

        Returns:
            Processed schemas with readOnly annotations
        """
        result = {}

        for schema_name, schema in schemas.items():
            self.stats.schemas_processed += 1
            result[schema_name] = self._process_schema(schema, schema_name)

        return result

    def _process_schema(self, schema: dict[str, Any], schema_name: str) -> dict[str, Any]:
        """Process a single schema and add readOnly to computed fields.

        Args:
            schema: Schema definition
            schema_name: Name of the schema

        Returns:
            Processed schema
        """
        if not isinstance(schema, dict):
            return schema

        result = schema.copy()

        # Check if this schema matches metadata or ObjectRef patterns
        is_metadata_schema = self._matches_patterns(schema_name, self.metadata_patterns)
        is_object_ref_schema = self._matches_patterns(schema_name, self.object_ref_patterns)

        if is_metadata_schema or is_object_ref_schema:
            self.stats.schemas_matched += 1
            if is_metadata_schema:
                self.stats.metadata_schemas_matched += 1
            if is_object_ref_schema:
                self.stats.object_ref_schemas_matched += 1

        # Process properties if present
        if "properties" in result and isinstance(result["properties"], dict):
            result["properties"] = self._process_properties(
                result["properties"],
                schema_name,
                is_metadata_schema,
                is_object_ref_schema,
            )

        # Recursively process nested schemas
        for key in ["items", "additionalProperties"]:
            if key in result and isinstance(result[key], dict):
                result[key] = self._process_schema(result[key], f"{schema_name}.{key}")

        for key in ["oneOf", "allOf", "anyOf"]:
            if key in result and isinstance(result[key], list):
                result[key] = [
                    self._process_schema(item, f"{schema_name}.{key}[{i}]")
                    for i, item in enumerate(result[key])
                ]

        return result

    def _matches_patterns(self, schema_name: str, patterns: list[re.Pattern]) -> bool:
        """Check if schema name matches any of the given patterns.

        Args:
            schema_name: Name of the schema to check
            patterns: List of compiled regex patterns

        Returns:
            True if schema name matches any pattern
        """
        return any(pattern.search(schema_name) for pattern in patterns)

    def _process_properties(
        self,
        properties: dict[str, Any],
        schema_name: str,
        is_metadata_schema: bool,
        is_object_ref_schema: bool,
    ) -> dict[str, Any]:
        """Process properties and add readOnly to computed fields.

        Args:
            properties: Properties dictionary from schema
            schema_name: Name of parent schema
            is_metadata_schema: Whether parent schema matches metadata patterns
            is_object_ref_schema: Whether parent schema matches ObjectRef patterns

        Returns:
            Processed properties dictionary
        """
        result = {}

        for prop_name, prop_schema in properties.items():
            if not isinstance(prop_schema, dict):
                result[prop_name] = prop_schema
                continue

            result[prop_name] = prop_schema.copy()

            # Check if this field should be marked readOnly
            should_mark = False
            is_metadata_field = False

            # Check metadata fields (for metadata schemas)
            if is_metadata_schema and prop_name in self.metadata_fields:
                should_mark = True
                is_metadata_field = True

            # Check ObjectRef fields (for ObjectRef schemas)
            if is_object_ref_schema and prop_name in self.object_ref_fields:
                should_mark = True
                is_metadata_field = False

            # Apply readOnly if appropriate and not already set
            if should_mark and "readOnly" not in result[prop_name]:
                result[prop_name]["readOnly"] = True

                # Update stats
                if is_metadata_field:
                    self.stats.metadata_fields_marked += 1
                else:
                    self.stats.object_ref_fields_marked += 1

                # Track by field name
                if prop_name not in self.stats.fields_by_name:
                    self.stats.fields_by_name[prop_name] = 0
                self.stats.fields_by_name[prop_name] += 1

            # Recursively process nested properties
            if "properties" in result[prop_name]:
                nested_is_metadata = self._matches_patterns(
                    f"{schema_name}.{prop_name}",
                    self.metadata_patterns,
                )
                nested_is_ref = self._matches_patterns(
                    f"{schema_name}.{prop_name}",
                    self.object_ref_patterns,
                )
                result[prop_name]["properties"] = self._process_properties(
                    result[prop_name]["properties"],
                    f"{schema_name}.{prop_name}",
                    nested_is_metadata,
                    nested_is_ref,
                )

        return result

    def get_stats(self) -> dict[str, Any]:
        """Get enrichment statistics.

        Returns:
            Dictionary with enrichment metrics
        """
        return self.stats.to_dict()

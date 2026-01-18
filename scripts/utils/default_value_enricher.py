# Copyright (c) 2026 Robin Mordasiewicz. MIT License.

"""Server-applied default value enricher for OpenAPI specifications.

This enricher adds discovered server-applied default values to resource schemas,
enabling AI assistants and CLI tools to understand what values the server will
apply when fields are omitted.

Adds:
- OpenAPI standard 'default' field with the server-applied value
- x-f5xc-server-default: true marker to indicate the default is server-applied

Issue: #449 - Enrich API specs with server-applied default values
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .extension_constants import (
    X_F5XC_RECOMMENDED_ONEOF_VARIANT,
    X_F5XC_RECOMMENDED_VALUE,
    X_F5XC_SERVER_DEFAULT,
)

logger = logging.getLogger(__name__)


@dataclass
class DefaultValueEnrichmentStats:
    """Statistics for default value enrichment."""

    schemas_processed: int = 0
    schemas_matched: int = 0
    defaults_added: int = 0
    nested_defaults_added: int = 0
    recommended_added: int = 0
    nested_recommended_added: int = 0
    oneof_recommended_added: int = 0
    markers_added: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert stats to dictionary."""
        return {
            "schemas_processed": self.schemas_processed,
            "schemas_matched": self.schemas_matched,
            "defaults_added": self.defaults_added,
            "nested_defaults_added": self.nested_defaults_added,
            "recommended_added": self.recommended_added,
            "nested_recommended_added": self.nested_recommended_added,
            "oneof_recommended_added": self.oneof_recommended_added,
            "markers_added": self.markers_added,
            "error_count": len(self.errors),
            "errors": self.errors,
        }


class DefaultValueEnricher:
    """Enrich OpenAPI specs with discovered server-applied default values.

    Configuration-driven enricher that adds:
    - OpenAPI 'default' field with server-applied values
    - x-f5xc-server-default marker for tooling awareness

    Uses config/discovered_defaults.yaml for all definitions.
    """

    def __init__(self, config_path: Path | None = None) -> None:
        """Initialize enricher with configuration.

        Args:
            config_path: Optional path to config file.
                        Defaults to config/discovered_defaults.yaml
        """
        self.config_path = (
            config_path
            or Path(__file__).parent.parent.parent / "config" / "discovered_defaults.yaml"
        )
        self.config: dict[str, Any] = {}
        self.resources: dict[str, dict[str, Any]] = {}
        self.settings: dict[str, Any] = {}
        self.stats = DefaultValueEnrichmentStats()
        self._compiled_patterns: dict[str, re.Pattern[str]] = {}

        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from YAML file."""
        try:
            with self.config_path.open() as f:
                self.config = yaml.safe_load(f) or {}
                self.resources = self.config.get("resources", {})
                self.settings = self.config.get("settings", {})

                # Pre-compile regex patterns for performance
                for resource_name, resource_config in self.resources.items():
                    pattern = resource_config.get("schema_pattern")
                    if pattern:
                        try:
                            self._compiled_patterns[resource_name] = re.compile(pattern)
                        except re.error as e:
                            logger.warning(
                                "Invalid regex pattern for %s: %s - %s",
                                resource_name,
                                pattern,
                                e,
                            )

                logger.info("Loaded discovered_defaults from %s", self.config_path)
                logger.info("Found %d resource definitions", len(self.resources))
        except FileNotFoundError:
            logger.warning("Configuration file not found: %s", self.config_path)
            self.config = {}
            self.resources = {}
            self.settings = {}
        except yaml.YAMLError:
            logger.exception("Error parsing configuration")
            self.config = {}
            self.resources = {}
            self.settings = {}

    def enrich_spec(self, spec: dict[str, Any]) -> dict[str, Any]:
        """Enrich OpenAPI specification with server-applied default values.

        Args:
            spec: OpenAPI specification dictionary

        Returns:
            Enriched specification
        """
        if not self.resources:
            logger.debug("No resource definitions loaded, skipping default value enrichment")
            return spec

        schemas = spec.get("components", {}).get("schemas", {})
        logger.info("Enriching %d schemas with server-applied defaults", len(schemas))

        for schema_name, schema in schemas.items():
            self.stats.schemas_processed += 1
            self._enrich_schema(schema_name, schema, schemas)

        logger.info("Default value enrichment complete: %s", self.stats.to_dict())
        return spec

    def _enrich_schema(
        self,
        schema_name: str,
        schema: dict[str, Any],
        all_schemas: dict[str, Any],
    ) -> None:
        """Enrich individual schema with server-applied default values.

        Args:
            schema_name: Name of the schema
            schema: Schema definition
            all_schemas: All schemas from the spec for $ref resolution
        """
        resource_config = self._match_resource(schema_name)

        if not resource_config:
            return

        self.stats.schemas_matched += 1

        try:
            # Apply top-level defaults
            defaults = resource_config.get("defaults", {})
            self._apply_defaults_to_properties(schema, defaults)

            # Apply nested defaults
            nested = resource_config.get("nested", {})
            self._apply_nested_defaults(schema, nested, all_schemas)

            # Apply recommended values for required fields
            recommended = resource_config.get("recommended", {})
            self._apply_recommended_to_properties(schema, recommended)

            # Apply nested recommended values (within nested objects like http_health_check)
            self._apply_nested_recommended(schema, nested, all_schemas)

            # Apply OneOf recommended variants
            oneof_recommended = resource_config.get("oneof_recommended", {})
            self._apply_oneof_recommended(schema, oneof_recommended)

        except Exception as e:
            logger.exception("Error enriching schema %s with defaults", schema_name)
            self.stats.errors.append(
                {
                    "schema": schema_name,
                    "error": str(e),
                },
            )

    def _match_resource(self, schema_name: str) -> dict[str, Any] | None:
        """Match schema name to resource configuration.

        Uses pre-compiled regex patterns for efficient matching.

        Args:
            schema_name: Name of the schema to match

        Returns:
            Resource configuration if matched, None otherwise
        """
        for resource_name, pattern in self._compiled_patterns.items():
            if pattern.search(schema_name):
                return self.resources.get(resource_name, {})

        return None

    def _apply_defaults_to_properties(
        self,
        schema: dict[str, Any],
        defaults: dict[str, Any],
    ) -> None:
        """Apply default values to schema properties.

        Args:
            schema: Schema definition
            defaults: Dictionary of property_name -> default_value
        """
        properties = schema.get("properties", {})
        if not properties:
            return

        use_default = self.settings.get("use_openapi_default", True)
        add_marker = self.settings.get("add_marker_extension", True)

        for prop_name, default_value in defaults.items():
            if prop_name in properties:
                prop_schema = properties[prop_name]

                # Add OpenAPI standard 'default' field
                if use_default:
                    prop_schema["default"] = default_value
                    self.stats.defaults_added += 1

                # Add marker extension to indicate server-applied default
                if add_marker:
                    prop_schema[X_F5XC_SERVER_DEFAULT] = True
                    self.stats.markers_added += 1

    def _apply_nested_defaults(
        self,
        schema: dict[str, Any],
        nested: dict[str, dict[str, Any]],
        all_schemas: dict[str, Any],
    ) -> None:
        """Apply nested default values to schema properties.

        For nested objects like http_health_check within healthcheck,
        this applies defaults to properties within the nested object.
        Supports both inline properties and $ref references.

        Handles two config formats:
        1. Flat: {prop_name: default_value} - legacy format
        2. Structured: {defaults: {prop_name: default_value}, recommended: {...}}

        Args:
            schema: Schema definition
            nested: Dictionary of property_name -> nested config
            all_schemas: All schemas from the spec for $ref resolution
        """
        if not nested:
            return

        properties = schema.get("properties", {})
        if not properties:
            return

        use_default = self.settings.get("use_openapi_default", True)
        add_marker = self.settings.get("add_marker_extension", True)

        for parent_prop_name, nested_config in nested.items():
            if parent_prop_name not in properties:
                continue

            parent_prop = properties[parent_prop_name]

            # Handle inline object properties
            nested_properties = parent_prop.get("properties", {})

            # Handle $ref to another schema - resolve and apply to referenced schema
            if "$ref" in parent_prop:
                ref_path = parent_prop["$ref"]
                # Extract schema name from "#/components/schemas/healthcheckHttpHealthCheck"
                ref_schema_name = ref_path.split("/")[-1]
                if ref_schema_name in all_schemas:
                    ref_schema = all_schemas[ref_schema_name]
                    nested_properties = ref_schema.get("properties", {})

            if not nested_properties:
                continue

            # Handle structured format with 'defaults' sub-key
            if "defaults" in nested_config:
                nested_defaults = nested_config["defaults"]
            else:
                # Legacy flat format - entire nested_config is the defaults dict
                nested_defaults = nested_config

            for nested_prop_name, default_value in nested_defaults.items():
                if nested_prop_name in nested_properties:
                    nested_prop_schema = nested_properties[nested_prop_name]

                    if use_default:
                        nested_prop_schema["default"] = default_value
                        self.stats.nested_defaults_added += 1

                    if add_marker:
                        nested_prop_schema[X_F5XC_SERVER_DEFAULT] = True
                        self.stats.markers_added += 1

    def _apply_recommended_to_properties(
        self,
        schema: dict[str, Any],
        recommended: dict[str, Any],
    ) -> None:
        """Apply recommended values to schema properties.

        Recommended values are suggested values for required fields that match
        what the F5 XC web interface pre-populates. Unlike defaults (which are
        server-applied when omitted), recommended values are suggestions for
        fields that must be explicitly provided.

        Args:
            schema: Schema definition
            recommended: Dictionary of property_name -> recommended_value
        """
        if not recommended:
            return

        properties = schema.get("properties", {})
        if not properties:
            return

        for prop_name, recommended_value in recommended.items():
            if prop_name in properties:
                prop_schema = properties[prop_name]

                # Add x-f5xc-recommended-value extension
                prop_schema[X_F5XC_RECOMMENDED_VALUE] = recommended_value
                self.stats.recommended_added += 1

    def _apply_nested_recommended(
        self,
        schema: dict[str, Any],
        nested: dict[str, dict[str, Any]],
        all_schemas: dict[str, Any],
    ) -> None:
        """Apply recommended values to nested object properties.

        For nested objects like http_health_check within healthcheck,
        this applies x-f5xc-recommended-value to properties within the nested object.
        Supports both inline properties and $ref references.

        Only processes nested configs that have a 'recommended' sub-key.

        Args:
            schema: Schema definition
            nested: Dictionary of property_name -> nested config (with recommended sub-key)
            all_schemas: All schemas from the spec for $ref resolution
        """
        if not nested:
            return

        properties = schema.get("properties", {})
        if not properties:
            return

        for parent_prop_name, nested_config in nested.items():
            # Only process if there's a 'recommended' sub-key
            if "recommended" not in nested_config:
                continue

            if parent_prop_name not in properties:
                continue

            parent_prop = properties[parent_prop_name]

            # Handle inline object properties
            nested_properties = parent_prop.get("properties", {})

            # Handle $ref to another schema - resolve and apply to referenced schema
            if "$ref" in parent_prop:
                ref_path = parent_prop["$ref"]
                # Extract schema name from "#/components/schemas/healthcheckHttpHealthCheck"
                ref_schema_name = ref_path.split("/")[-1]
                if ref_schema_name in all_schemas:
                    ref_schema = all_schemas[ref_schema_name]
                    nested_properties = ref_schema.get("properties", {})

            if not nested_properties:
                continue

            nested_recommended = nested_config["recommended"]
            for nested_prop_name, recommended_value in nested_recommended.items():
                if nested_prop_name in nested_properties:
                    nested_prop_schema = nested_properties[nested_prop_name]
                    nested_prop_schema[X_F5XC_RECOMMENDED_VALUE] = recommended_value
                    self.stats.nested_recommended_added += 1

    def _apply_oneof_recommended(
        self,
        schema: dict[str, Any],
        oneof_recommended: dict[str, str],
    ) -> None:
        """Apply recommended OneOf variant extension to schema.

        For schemas with OneOf fields (like health_check with http_health_check,
        tcp_health_check variants), this marks the recommended variant.

        The x-f5xc-recommended-oneof-variant extension is added at the schema level
        for each OneOf group, indicating which variant is recommended.

        Args:
            schema: Schema definition
            oneof_recommended: Dictionary of oneof_group_name -> recommended_variant
        """
        if not oneof_recommended:
            return

        # Add the recommended OneOf variants at the schema level
        for oneof_group, recommended_variant in oneof_recommended.items():
            # Store as a nested dict keyed by group name
            if X_F5XC_RECOMMENDED_ONEOF_VARIANT not in schema:
                schema[X_F5XC_RECOMMENDED_ONEOF_VARIANT] = {}
            schema[X_F5XC_RECOMMENDED_ONEOF_VARIANT][oneof_group] = recommended_variant
            self.stats.oneof_recommended_added += 1

    def get_stats(self) -> dict[str, Any]:
        """Get enrichment statistics.

        Returns:
            Statistics dictionary
        """
        return self.stats.to_dict()

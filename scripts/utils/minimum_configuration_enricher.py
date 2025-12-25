"""Minimum configuration metadata enricher for OpenAPI specifications.

This enricher adds minimum configuration metadata to resource schemas,
enabling AI assistants and CLI tools to generate working configurations.

Adds four OpenAPI extensions:
- x-ves-minimum-configuration: Schema-level minimum config definition
- x-ves-required-for: Field-level context requirements
- x-ves-cli-domain: Domain classification for CLI routing
- x-ves-cli-aliases: Alternative names for resources
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .domain_categorizer import DomainCategorizer

logger = logging.getLogger(__name__)


@dataclass
class MinimumConfigurationStats:
    """Statistics for minimum configuration enrichment."""

    schemas_enriched: int = 0
    schemas_auto_generated: int = 0
    minimum_configs_added: int = 0
    minimum_configs_auto_generated: int = 0
    required_fields_added: int = 0
    field_requirements_added: int = 0
    example_yamls_generated: int = 0
    example_commands_generated: int = 0
    cli_domains_added: int = 0
    cli_domains_preserved: int = 0
    cli_aliases_added: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert stats to dictionary."""
        return {
            "schemas_enriched": self.schemas_enriched,
            "schemas_auto_generated": self.schemas_auto_generated,
            "minimum_configs_added": self.minimum_configs_added,
            "minimum_configs_auto_generated": self.minimum_configs_auto_generated,
            "required_fields_added": self.required_fields_added,
            "field_requirements_added": self.field_requirements_added,
            "example_yamls_generated": self.example_yamls_generated,
            "example_commands_generated": self.example_commands_generated,
            "cli_domains_added": self.cli_domains_added,
            "cli_domains_preserved": self.cli_domains_preserved,
            "cli_aliases_added": self.cli_aliases_added,
            "error_count": len(self.errors),
            "errors": self.errors,
        }


class MinimumConfigurationEnricher:
    """Enrich OpenAPI specs with minimum configuration metadata.

    Configuration-driven enricher that adds:
    - Minimum viable configuration examples for each resource
    - Required fields for functional configurations
    - CLI metadata for xcsh integration
    - Domain and resource type classification

    Uses config/minimum_configs.yaml for all definitions.
    Uses DomainCategorizer singleton for domain auto-mapping.
    """

    def __init__(self, config_path: Path | None = None) -> None:
        """Initialize enricher with configuration.

        Args:
            config_path: Optional path to config file.
                        Defaults to config/minimum_configs.yaml
        """
        self.config_path = (
            config_path or Path(__file__).parent.parent.parent / "config" / "minimum_configs.yaml"
        )
        self.domain_categorizer = DomainCategorizer()
        self.config: dict[str, Any] = {}
        self.resources: dict[str, dict[str, Any]] = {}
        self.stats = MinimumConfigurationStats()

        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from YAML file."""
        try:
            with self.config_path.open() as f:
                self.config = yaml.safe_load(f) or {}
                self.resources = self.config.get("resources", {})
                logger.info("Loaded minimum_configs from %s", self.config_path)
                logger.info("Found %d resource definitions", len(self.resources))
        except FileNotFoundError:
            logger.exception("Configuration file not found: %s", self.config_path)
            self.config = {}
            self.resources = {}
        except yaml.YAMLError:
            logger.exception("Error parsing configuration")
            self.config = {}
            self.resources = {}

    def enrich_spec(self, spec: dict[str, Any]) -> dict[str, Any]:
        """Enrich OpenAPI specification with minimum configuration metadata.

        Args:
            spec: OpenAPI specification dictionary

        Returns:
            Enriched specification
        """
        if not self.resources:
            logger.warning("No resource definitions loaded, skipping enrichment")
            return spec

        schemas = spec.get("components", {}).get("schemas", {})
        logger.info("Enriching %d schemas with minimum configuration metadata", len(schemas))
        for schema_name, schema in schemas.items():
            self._enrich_schema(schema_name, schema)

        logger.info("Minimum configuration enrichment complete: %s", self.stats.to_dict())
        return spec

    def _enrich_schema(
        self,
        schema_name: str,
        schema: dict[str, Any],
    ) -> None:
        """Enrich individual schema with minimum configuration metadata.

        Handles both configured resources (from config/minimum_configs.yaml) and
        unconfigured resources (via auto-generation). x-ves-cli-domain is idempotent
        and will preserve existing values.

        Args:
            schema_name: Name of the schema
            schema: Schema definition
        """
        resource_type = self._detect_resource_type(schema_name)

        try:
            # Check if x-ves-cli-domain already exists (idempotent behavior)
            has_existing_cli_domain = "x-ves-cli-domain" in schema

            if resource_type and resource_type in self.resources:
                # Explicit configuration exists
                resource_config = self.resources[resource_type]
                self._enrich_from_config(schema, schema_name, resource_type, resource_config)
            else:
                # Auto-generate for unconfigured resources
                self._enrich_with_auto_generation(schema, schema_name, resource_type)
                self.stats.schemas_auto_generated += 1

            # Preserve existing x-ves-cli-domain or add domain via categorizer
            if not has_existing_cli_domain or "x-ves-cli-domain" not in schema:
                domain = self._get_domain_for_resource(resource_type or "", schema_name)
                schema["x-ves-cli-domain"] = domain
                self.stats.cli_domains_added += 1
            else:
                self.stats.cli_domains_preserved += 1

            self.stats.schemas_enriched += 1

        except Exception as e:
            logger.exception("Error enriching schema %s", schema_name)
            self.stats.errors.append(
                {
                    "schema": schema_name,
                    "error": str(e),
                    "resource_type": resource_type,
                },
            )

    def _enrich_from_config(
        self,
        schema: dict[str, Any],
        _schema_name: str,
        resource_type: str | None,
        resource_config: dict[str, Any],
    ) -> None:
        """Enrich schema using explicit configuration.

        Args:
            schema: Schema to enrich
            _schema_name: Schema name
            resource_type: Detected resource type
            resource_config: Configuration from config file
        """
        # Add x-ves-minimum-configuration at schema level
        minimum_config = {
            "description": resource_config.get("description", ""),
            "required_fields": self._extract_required_fields(resource_type, schema),
            "mutually_exclusive_groups": resource_config.get("mutually_exclusive_groups", []),
            "example_yaml": resource_config.get("example_yaml", ""),
            "example_command": resource_config.get("example_command", ""),
        }

        schema["x-ves-minimum-configuration"] = minimum_config
        self.stats.minimum_configs_added += 1

        # Add x-ves-required-for to schema properties
        self._add_field_requirements(schema, resource_config)

        # Add x-ves-cli-aliases if configured
        if "cli" in resource_config and "aliases" in resource_config["cli"]:
            schema["x-ves-cli-aliases"] = resource_config["cli"]["aliases"]
            self.stats.cli_aliases_added += 1

    def _enrich_with_auto_generation(
        self,
        schema: dict[str, Any],
        schema_name: str,
        _resource_type: str | None,
    ) -> None:
        """Auto-generate minimum configuration for unconfigured resources.

        Args:
            schema: Schema to enrich
            schema_name: Schema name
            _resource_type: Detected or inferred resource type
        """
        # Generate sensible defaults
        auto_config = self._auto_generate_minimum_config(schema, schema_name)

        schema["x-ves-minimum-configuration"] = auto_config
        self.stats.minimum_configs_auto_generated += 1

        # Add basic field requirements
        self._add_auto_generated_field_requirements(schema)

    def _auto_generate_minimum_config(
        self,
        schema: dict[str, Any],
        schema_name: str,
    ) -> dict[str, Any]:
        """Auto-generate minimum configuration from schema inspection.

        Args:
            schema: OpenAPI schema
            schema_name: Schema name

        Returns:
            Generated minimum configuration dictionary
        """
        required_fields = self._extract_required_fields_from_schema(schema)
        example_yaml = self._generate_example_yaml(schema_name, required_fields)
        example_command = self._generate_example_command(schema_name)

        return {
            "description": f"Minimum configuration for {schema_name}",
            "required_fields": required_fields,
            "mutually_exclusive_groups": [],
            "example_yaml": example_yaml,
            "example_command": example_command,
        }

    def _extract_required_fields_from_schema(self, schema: dict[str, Any]) -> list[str]:
        """Extract required fields directly from schema.

        Args:
            schema: OpenAPI schema

        Returns:
            List of required field names
        """
        # Get required array from schema if present
        required = schema.get("required", [])

        # If no required fields, use all properties as fallback
        if not required:
            properties = schema.get("properties", {})
            if properties:
                required = list(properties.keys())

        return required

    def _generate_example_yaml(self, schema_name: str, required_fields: list[str]) -> str:
        """Generate example YAML from schema information.

        Args:
            schema_name: Schema name
            required_fields: List of required field names

        Returns:
            Generated example YAML string
        """
        lines = [
            "# Minimal example for " + schema_name,
            "metadata:",
            "  name: example",
            "  namespace: default",
        ]

        if required_fields:
            lines.append("spec:")
            spec_fields = [
                f"  {field}: value"
                for field in required_fields[:5]
                if field not in ["metadata", "apiVersion", "kind"]
            ]
            lines.extend(spec_fields)

        return "\n".join(lines)

    def _generate_example_command(self, schema_name: str) -> str:
        """Generate example xcsh CLI command.

        Args:
            schema_name: Schema name

        Returns:
            Example CLI command
        """
        # Infer resource type from schema name
        resource_name = (
            schema_name.split("Create")[0].split("Update")[0].split("Get")[0].split("Delete")[0]
        )
        resource_name = re.sub(r"(?<!^)(?=[A-Z])", "_", resource_name).lower()

        # Infer domain (default to "virtual")
        domain = "virtual"
        if "waf" in resource_name or "firewall" in resource_name:
            domain = "waf"
        elif "cdn" in resource_name:
            domain = "cdn"

        return f"xcsh {domain} create {resource_name} -n default -f example.yaml"

    def _add_auto_generated_field_requirements(self, schema: dict[str, Any]) -> None:
        """Add basic x-ves-required-for to schema properties (auto-generated).

        Args:
            schema: Schema definition
        """
        properties = schema.get("properties", {})
        if not properties:
            return

        required_list = schema.get("required", [])

        for field_name, field_schema in properties.items():
            if not isinstance(field_schema, dict):
                continue

            is_required = field_name in required_list
            field_requirements = {
                "minimum_config": is_required,
                "create": is_required,
                "update": False,
                "read": False,
            }
            field_schema["x-ves-required-for"] = field_requirements
            self.stats.field_requirements_added += 1

    def _detect_resource_type(self, schema_name: str) -> str | None:
        """Detect resource type from schema name.

        Maps schema names to resource types defined in config.
        Handles variations like CreateSpecType, UpdateSpecType, viewshttp_loadbalancerCreateSpecType.

        Args:
            schema_name: Name of the schema

        Returns:
            Resource type if found, None otherwise
        """
        # Direct match
        if schema_name in self.resources:
            return schema_name

        # Remove common prefixes (e.g., "views", "api", "schema")
        working_name = schema_name
        for prefix in ["views", "api", "schema"]:
            if working_name.startswith(prefix):
                working_name = working_name[len(prefix) :]
                break

        # Remove common suffixes in order of specificity
        for suffix in [
            "CreateSpecType",
            "UpdateSpecType",
            "GetSpecType",
            "DeleteSpecType",
            "SpecType",
            "Spec",
            "Type",
            "Request",
            "Response",
            "Create",
            "Update",
        ]:
            if working_name.endswith(suffix):
                base_name = working_name[: -len(suffix)]
                if base_name in self.resources:
                    return base_name

        # Try converting case variations (e.g., HttpLoadbalancer -> http_loadbalancer)
        snake_case = re.sub(r"(?<!^)(?=[A-Z])", "_", working_name).lower()
        if snake_case in self.resources:
            return snake_case

        # Try partial matching for compound names
        for resource in self.resources:
            if resource in working_name.lower():
                return resource

        return None

    def _extract_required_fields(
        self,
        resource_type: str | None,
        schema: dict[str, Any],
    ) -> list[str]:
        """Extract minimum required fields for resource.

        Uses config-defined required fields if present.
        Falls back to schema's required array.

        Args:
            resource_type: Type of resource
            schema: Schema definition

        Returns:
            List of required field names
        """
        # Use config-defined required fields if present
        if resource_type:
            config_required = self.resources.get(resource_type, {}).get("required_fields", [])
            if config_required:
                self.stats.required_fields_added += 1
                return config_required

        # Fallback to schema required array
        return schema.get("required", [])

    def _add_field_requirements(
        self,
        schema: dict[str, Any],
        resource_config: dict[str, Any],
    ) -> None:
        """Add x-ves-required-for to schema properties.

        Args:
            schema: Schema definition
            resource_config: Resource configuration from config file
        """
        properties = schema.get("properties", {})
        if not properties:
            return

        required_fields = self._extract_required_fields_list(resource_config)

        for field_name, field_schema in properties.items():
            if not isinstance(field_schema, dict):
                continue
            is_required = field_name in required_fields
            field_requirements = {
                "minimum_config": is_required,
                "create": is_required,
                "update": False,
                "read": False,
            }
            field_schema["x-ves-required-for"] = field_requirements
            self.stats.field_requirements_added += 1

    def _extract_required_fields_list(self, resource_config: dict[str, Any]) -> list[str]:
        """Extract required fields list from resource config.

        Args:
            resource_config: Resource configuration

        Returns:
            List of required field names
        """
        required = resource_config.get("required_fields", [])
        # Convert nested paths (e.g., "metadata.name") to top-level field names for property matching
        field_names = []
        for field_path in required:
            # Get the top-level field name
            top_level = field_path.split(".")[0]
            if top_level not in field_names:
                field_names.append(top_level)
        return field_names

    def _get_domain_for_resource(self, resource_type: str, schema_name: str) -> str:
        """Get domain classification for resource.

        Priority:
        1. Explicit domain in config
        2. DomainCategorizer mapping
        3. Resource name inference
        4. Fallback

        Args:
            resource_type: Type of resource
            schema_name: Schema name for categorizer

        Returns:
            Domain classification
        """
        # Check config
        config_domain = self.resources.get(resource_type, {}).get("domain")
        if config_domain:
            return config_domain

        # Try DomainCategorizer
        try:
            domain = self.domain_categorizer.categorize(schema_name)
            if domain:
                return domain
        except Exception as e:
            logger.debug("DomainCategorizer failed for %s: %s", schema_name, e)

        # Fallback: infer from resource type
        if "virtual" in resource_type.lower() or "loadbalancer" in resource_type.lower():
            return "virtual"
        if "waf" in resource_type.lower() or "firewall" in resource_type.lower():
            return "waf"
        if "pool" in resource_type.lower():
            return "virtual"

        return "other"

    def get_stats(self) -> dict[str, Any]:
        """Get enrichment statistics.

        Returns:
            Statistics dictionary
        """
        return self.stats.to_dict()

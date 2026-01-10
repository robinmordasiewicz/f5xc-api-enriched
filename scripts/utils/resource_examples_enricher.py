# Copyright (c) 2026 Robin Mordasiewicz. MIT License.

"""Resource Examples Enricher for OpenAPI specifications.

Provides tiered resource configuration examples (minimal, production, advanced, migration)
with optional validation against OpenAPI schemas.

The examples extension helps AI assistants and CLI tools provide
contextual configuration snippets for different deployment scenarios.

Issue: #325

Usage:
    enricher = ResourceExamplesEnricher()
    spec_entry = enricher.enrich_index_entry(spec_entry, domain, schemas)
    stats = enricher.get_stats()
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .extension_constants import X_F5XC_EXAMPLES


@dataclass
class ResourceExamplesEnrichmentStats:
    """Statistics from resource examples enrichment."""

    domains_processed: int = 0
    domains_with_examples: int = 0
    resources_with_examples: int = 0
    examples_added: int = 0
    examples_validated: int = 0
    validation_failures: int = 0
    validation_warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert stats to dictionary."""
        return {
            "domains_processed": self.domains_processed,
            "domains_with_examples": self.domains_with_examples,
            "resources_with_examples": self.resources_with_examples,
            "examples_added": self.examples_added,
            "examples_validated": self.examples_validated,
            "validation_failures": self.validation_failures,
            "validation_warnings_count": len(self.validation_warnings),
        }


@dataclass
class ResourceExample:
    """Single resource configuration example."""

    description: str
    use_case: str
    yaml_content: str
    validated: bool = True
    validation_errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {
            "description": self.description,
            "use_case": self.use_case,
            "yaml": self.yaml_content,
        }
        if not self.validated:
            result["validated"] = False
            if self.validation_errors:
                result["validation_errors"] = self.validation_errors
        return result


@dataclass
class ResourceExamples:
    """All tier examples for a single resource."""

    minimal: ResourceExample | None = None
    production: ResourceExample | None = None
    advanced: ResourceExample | None = None
    migration: ResourceExample | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with only non-None tiers."""
        result = {}
        if self.minimal:
            result["minimal"] = self.minimal.to_dict()
        if self.production:
            result["production"] = self.production.to_dict()
        if self.advanced:
            result["advanced"] = self.advanced.to_dict()
        if self.migration:
            result["migration"] = self.migration.to_dict()
        return result

    def is_empty(self) -> bool:
        """Check if no examples are defined."""
        return not any([self.minimal, self.production, self.advanced, self.migration])

    def count_tiers(self) -> int:
        """Count number of defined tiers."""
        return sum(
            1
            for tier in [self.minimal, self.production, self.advanced, self.migration]
            if tier is not None
        )


class ExampleValidator:
    """Validates YAML examples against OpenAPI schemas.

    Uses jsonschema library to validate parsed YAML content against
    the corresponding resource schema from the OpenAPI specification.
    """

    def __init__(self, schemas: dict[str, Any]) -> None:
        """Initialize validator with schemas from OpenAPI spec.

        Args:
            schemas: Dictionary of schema_name -> schema_definition
        """
        self.schemas = schemas
        self._jsonschema_available = self._check_jsonschema()

    def _check_jsonschema(self) -> bool:
        """Check if jsonschema library is available."""
        try:
            import jsonschema  # noqa: F401, PLC0415

            return True
        except ImportError:
            return False

    def validate_example(
        self,
        yaml_content: str,
        resource_name: str,
        schema_name: str | None = None,
    ) -> tuple[bool, list[str]]:
        """Validate YAML example against schema.

        Args:
            yaml_content: YAML string to validate
            resource_name: Resource name (e.g., "http_loadbalancer")
            schema_name: Optional explicit schema name to validate against

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors: list[str] = []

        # Parse YAML first
        try:
            example_data = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            return False, [f"YAML parse error: {e}"]

        if example_data is None:
            return False, ["Empty YAML content"]

        # If jsonschema not available, skip validation
        if not self._jsonschema_available:
            return True, ["jsonschema not available, skipping validation"]

        # Find matching schema
        target_schema_name = schema_name or self._find_schema_name(resource_name)
        if not target_schema_name or target_schema_name not in self.schemas:
            # No schema found - can't validate, return success with note
            return True, [f"No schema found for {resource_name}, skipping validation"]

        schema = self.schemas[target_schema_name]

        # Validate spec portion (skip metadata which may not be in schema)
        spec_data = example_data.get("spec", example_data)

        try:
            import jsonschema  # noqa: PLC0415

            # Build a resolver for $ref handling
            schema_store = {f"#/components/schemas/{name}": s for name, s in self.schemas.items()}
            resolver = jsonschema.RefResolver.from_schema(
                {"components": {"schemas": self.schemas}},
                store=schema_store,
            )

            validator = jsonschema.Draft7Validator(schema, resolver=resolver)
            validation_errors = list(validator.iter_errors(spec_data))

            if validation_errors:
                # Limit to first 5 errors to avoid noise
                errors = [
                    f"{'.'.join(str(p) for p in e.path) or 'root'}: {e.message}"
                    for e in validation_errors[:5]
                ]
                return False, errors

            return True, []

        except jsonschema.exceptions.SchemaError as e:
            return True, [f"Schema error (skipping validation): {e.message}"]
        except Exception as e:
            return True, [f"Validation error (skipping): {e!s}"]

    def _find_schema_name(self, resource_name: str) -> str | None:
        """Find schema name for resource.

        Looks for patterns like:
        - {resource}CreateRequest
        - {resource}Type
        - {resource}

        Args:
            resource_name: Resource name (e.g., "http_loadbalancer")

        Returns:
            Schema name if found, None otherwise
        """
        patterns = [
            f"{resource_name}CreateRequest",
            f"{resource_name}Type",
            resource_name,
            resource_name.replace("_", ""),
        ]

        for pattern in patterns:
            # Case-insensitive search
            for schema_name in self.schemas:
                if schema_name.lower() == pattern.lower():
                    return schema_name

        return None


class ResourceExamplesEnricher:
    """Enrich index entries with tiered resource examples.

    Loads examples from config/resource_examples.yaml, optionally validates
    against OpenAPI schemas, and adds x-f5xc-examples extension to index entries.

    Examples are organized by:
    - Domain (virtual, waf, dns, etc.)
    - Resource (http_loadbalancer, origin_pool, etc.)
    - Tier (minimal, production, advanced, migration)

    Attributes:
        config_path: Path to resource_examples.yaml
        domains: Dictionary of domain -> {resource -> ResourceExamples}
        stats: Enrichment statistics
    """

    def __init__(self, config_path: Path | None = None) -> None:
        """Initialize enricher with examples configuration.

        Args:
            config_path: Path to resource_examples.yaml config.
                        Defaults to config/resource_examples.yaml.
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "resource_examples.yaml"

        self.config_path = config_path
        self.domains: dict[str, dict[str, ResourceExamples]] = {}
        self.stats = ResourceExamplesEnrichmentStats()
        self._config_version: str = "0.0.0"
        self._validate_examples: bool = True

        self._load_config()

    def _load_config(self) -> None:
        """Load examples configuration from YAML file."""
        if not self.config_path.exists():
            # No config file - will skip enrichment gracefully
            return

        try:
            with self.config_path.open() as f:
                config = yaml.safe_load(f) or {}

            self._config_version = config.get("version", "0.0.0")

            # Load domain-specific examples
            domains_config = config.get("domains", {})
            for domain_name, resources in domains_config.items():
                if not isinstance(resources, dict):
                    continue

                self.domains[domain_name] = {}
                for resource_name, tiers in resources.items():
                    if not isinstance(tiers, dict):
                        continue

                    self.domains[domain_name][resource_name] = self._parse_resource_examples(
                        tiers,
                        resource_name,
                    )

        except yaml.YAMLError:
            # Invalid YAML - skip enrichment gracefully
            pass

    def _parse_resource_examples(
        self,
        tiers: dict[str, Any],
        _resource_name: str,
    ) -> ResourceExamples:
        """Parse tier examples for a resource.

        Args:
            tiers: Dictionary of tier_name -> tier_config
            _resource_name: Name of the resource (reserved for logging)

        Returns:
            ResourceExamples with parsed tiers
        """
        examples = ResourceExamples()

        for tier_name in ["minimal", "production", "advanced", "migration"]:
            tier_config = tiers.get(tier_name)
            if not tier_config or not isinstance(tier_config, dict):
                continue

            yaml_content = tier_config.get("yaml", "")
            if not yaml_content:
                continue

            example = ResourceExample(
                description=tier_config.get("description", ""),
                use_case=tier_config.get("use_case", ""),
                yaml_content=yaml_content,
            )

            setattr(examples, tier_name, example)

        return examples

    def get_examples_for_domain(self, domain: str) -> dict[str, ResourceExamples]:
        """Get all resource examples for a domain.

        Args:
            domain: Domain name (e.g., "virtual")

        Returns:
            Dictionary of resource_name -> ResourceExamples
        """
        return self.domains.get(domain, {})

    def get_examples_for_resource(
        self,
        domain: str,
        resource: str,
    ) -> ResourceExamples | None:
        """Get examples for a specific resource.

        Args:
            domain: Domain name (e.g., "virtual")
            resource: Resource name (e.g., "http_loadbalancer")

        Returns:
            ResourceExamples if found, None otherwise
        """
        return self.domains.get(domain, {}).get(resource)

    def validate_examples(
        self,
        domain: str,
        schemas: dict[str, Any],
    ) -> dict[str, ResourceExamples]:
        """Validate all examples for a domain against schemas.

        Validates each example's YAML content against the corresponding
        OpenAPI schema. Validation failures are recorded but do not
        prevent examples from being included (graceful degradation).

        Args:
            domain: Domain name
            schemas: OpenAPI schemas from spec

        Returns:
            Dictionary of resource -> validated ResourceExamples
        """
        validator = ExampleValidator(schemas)
        domain_examples = self.get_examples_for_domain(domain)

        for resource_name, examples in domain_examples.items():
            for tier_name in ["minimal", "production", "advanced", "migration"]:
                example = getattr(examples, tier_name)
                if example and example.yaml_content:
                    is_valid, errors = validator.validate_example(
                        example.yaml_content,
                        resource_name,
                    )
                    example.validated = is_valid
                    example.validation_errors = errors

                    if is_valid:
                        self.stats.examples_validated += 1
                    else:
                        self.stats.validation_failures += 1
                        for error in errors:
                            warning = f"{domain}/{resource_name}/{tier_name}: {error}"
                            self.stats.validation_warnings.append(warning)

        return domain_examples

    def enrich_index_entry(
        self,
        spec_entry: dict[str, Any],
        domain: str,
        schemas: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Enrich a spec index entry with validated examples.

        Adds x-f5xc-examples extension to the spec entry if examples
        are configured for the domain.

        Args:
            spec_entry: Index entry dictionary to enrich
            domain: Domain name
            schemas: OpenAPI schemas for validation (optional)

        Returns:
            Enriched spec entry with x-f5xc-examples
        """
        self.stats.domains_processed += 1

        # Get examples for this domain
        domain_examples = self.get_examples_for_domain(domain)

        if not domain_examples:
            return spec_entry

        # Validate if schemas provided
        if schemas and self._validate_examples:
            domain_examples = self.validate_examples(domain, schemas)

        # Build x-f5xc-examples structure
        examples_dict: dict[str, Any] = {}
        for resource_name, examples in domain_examples.items():
            if not examples.is_empty():
                examples_dict[resource_name] = examples.to_dict()
                self.stats.resources_with_examples += 1
                self.stats.examples_added += examples.count_tiers()

        if examples_dict:
            spec_entry[X_F5XC_EXAMPLES] = examples_dict
            self.stats.domains_with_examples += 1

        return spec_entry

    def has_examples(self, domain: str) -> bool:
        """Check if examples exist for a domain.

        Args:
            domain: Domain name to check

        Returns:
            True if examples are configured for the domain
        """
        return domain in self.domains and bool(self.domains[domain])

    def get_configured_domains(self) -> list[str]:
        """Get list of domains with configured examples.

        Returns:
            Sorted list of domain names
        """
        return sorted(self.domains.keys())

    def get_config_version(self) -> str:
        """Get version of loaded examples configuration.

        Returns:
            Version string from config (e.g., "1.0.0")
        """
        return self._config_version

    def get_stats(self) -> dict[str, Any]:
        """Get enrichment statistics.

        Returns:
            Dictionary with enrichment metrics
        """
        return self.stats.to_dict()

    def set_validation_enabled(self, enabled: bool) -> None:
        """Enable or disable example validation.

        Args:
            enabled: True to enable validation, False to skip
        """
        self._validate_examples = enabled


__all__ = [
    "ExampleValidator",
    "ResourceExample",
    "ResourceExamples",
    "ResourceExamplesEnricher",
    "ResourceExamplesEnrichmentStats",
]

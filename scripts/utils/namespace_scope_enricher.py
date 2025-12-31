"""Namespace scope metadata enricher for OpenAPI specifications.

This enricher adds namespace scope metadata to OpenAPI specs,
indicating which namespaces each resource type can be created in.

Adds the x-ves-namespace-scope extension with values:
- system: Only available in system namespace
- shared: Only available in shared namespace
- any: Available in user namespaces (shared, default, custom) but NOT system

Configuration is loaded from config/namespace_scope.yaml.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass
class NamespaceScopeStats:
    """Statistics for namespace scope enrichment."""

    specs_enriched: int = 0
    system_scoped: int = 0
    shared_scoped: int = 0
    any_scoped: int = 0
    already_had_scope: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert stats to dictionary."""
        return {
            "specs_enriched": self.specs_enriched,
            "system_scoped": self.system_scoped,
            "shared_scoped": self.shared_scoped,
            "any_scoped": self.any_scoped,
            "already_had_scope": self.already_had_scope,
            "error_count": len(self.errors),
            "errors": self.errors,
        }


class NamespaceScopeEnricher:
    """Enrich OpenAPI specs with namespace scope metadata.

    Adds x-ves-namespace-scope extension to the spec's info section,
    indicating which namespaces the resource type can be created in.

    Uses config/namespace_scope.yaml for scope mappings.
    """

    def __init__(self, config_path: Path | None = None) -> None:
        """Initialize enricher with configuration.

        Args:
            config_path: Optional path to config file.
                        Defaults to config/namespace_scope.yaml
        """
        self.config_path = (
            config_path or Path(__file__).parent.parent.parent / "config" / "namespace_scope.yaml"
        )
        self.config: dict[str, Any] = {}
        self.extension_name: str = "x-ves-namespace-scope"
        self.default_scope: str = "any"
        self.system_resources: set[str] = set()
        self.shared_resources: set[str] = set()
        self.stats = NamespaceScopeStats()

        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from YAML file."""
        try:
            with self.config_path.open() as f:
                self.config = yaml.safe_load(f) or {}
                self.extension_name = self.config.get("extension_name", "x-ves-namespace-scope")
                self.default_scope = self.config.get("default_scope", "any")

                scopes = self.config.get("scopes", {})
                self.system_resources = set(scopes.get("system", []))
                self.shared_resources = set(scopes.get("shared", []))

                logger.info("Loaded namespace_scope config from %s", self.config_path)
                logger.info(
                    "Found %d system-scoped, %d shared-scoped resources",
                    len(self.system_resources),
                    len(self.shared_resources),
                )
        except FileNotFoundError:
            logger.warning("Configuration file not found: %s", self.config_path)
            self.config = {}
        except yaml.YAMLError:
            logger.exception("Error parsing configuration")
            self.config = {}

    def enrich_spec(self, spec: dict[str, Any]) -> dict[str, Any]:
        """Enrich OpenAPI specification with namespace scope metadata.

        Adds x-ves-namespace-scope to the spec's info section based on
        the resource type detected from the spec title or paths.

        Args:
            spec: OpenAPI specification dictionary

        Returns:
            Enriched specification
        """
        try:
            info = spec.get("info", {})

            # Check if already enriched (idempotent)
            if self.extension_name in info:
                self.stats.already_had_scope += 1
                self.stats.specs_enriched += 1
                return spec

            # Detect resource type from spec
            resource_type = self._detect_resource_type(spec)
            scope = self._determine_scope(resource_type)

            # Add scope to info section
            if "info" not in spec:
                spec["info"] = {}
            spec["info"][self.extension_name] = scope

            # Update stats
            self.stats.specs_enriched += 1
            if scope == "system":
                self.stats.system_scoped += 1
            elif scope == "shared":
                self.stats.shared_scoped += 1
            else:
                self.stats.any_scoped += 1

            logger.debug(
                "Added %s=%s for resource type '%s'",
                self.extension_name,
                scope,
                resource_type,
            )

        except Exception as e:
            logger.exception("Error enriching spec with namespace scope")
            self.stats.errors.append(
                {
                    "error": str(e),
                    "spec_title": spec.get("info", {}).get("title", "unknown"),
                },
            )

        return spec

    def _detect_resource_type(self, spec: dict[str, Any]) -> str:
        """Detect resource type from OpenAPI specification.

        Uses multiple strategies to determine the resource type:
        1. Extract from spec title (e.g., "Alert Policy API" -> "alert_policy")
        2. Extract from first path (e.g., "/api/.../alert_policy/..." -> "alert_policy")
        3. Extract from x-ves-cli-domain or other extensions

        Args:
            spec: OpenAPI specification

        Returns:
            Detected resource type in snake_case
        """
        # Strategy 1: Extract from title
        title = spec.get("info", {}).get("title", "")
        if title:
            resource_type = self._extract_resource_from_title(title)
            if resource_type:
                return resource_type

        # Strategy 2: Extract from paths
        paths = spec.get("paths", {})
        if paths:
            resource_type = self._extract_resource_from_paths(paths)
            if resource_type:
                return resource_type

        # Strategy 3: Use x-ves-cli-domain if present
        domain = spec.get("info", {}).get("x-ves-cli-domain", "")
        if domain:
            return domain

        return ""

    def _extract_resource_from_title(self, title: str) -> str:
        """Extract resource type from API title.

        Examples:
            "Alert Policy API" -> "alert_policy"
            "HTTP Load Balancer API" -> "http_loadbalancer"
            "AWS VPC Site API" -> "aws_vpc_site"

        Args:
            title: API title string

        Returns:
            Resource type in snake_case
        """
        # Remove common suffixes
        title = re.sub(r"\s+API\s*$", "", title, flags=re.IGNORECASE)
        title = re.sub(r"\s+Service\s*$", "", title, flags=re.IGNORECASE)

        # Convert to snake_case
        # First handle acronyms (uppercase sequences followed by uppercase+lowercase)
        title = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", title)
        # Then handle regular camelCase
        title = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", title)
        # Replace spaces and hyphens with underscores
        title = re.sub(r"[\s\-]+", "_", title)
        # Convert to lowercase and clean up
        resource_type = title.lower().strip("_")
        # Remove duplicate underscores and return
        return re.sub(r"_+", "_", resource_type)

    def _extract_resource_from_paths(self, paths: dict[str, Any]) -> str:
        """Extract resource type from API paths.

        Looks for common F5 XC path patterns like:
            /api/config/namespaces/{namespace}/alert_policys
            /web/namespaces/{namespace}/origin_pools

        Args:
            paths: OpenAPI paths object

        Returns:
            Resource type in snake_case
        """
        for path in paths:
            # Look for resource type after namespaces/{namespace}/
            match = re.search(
                r"/namespaces/\{[^}]+\}/([a-z][a-z0-9_]*?)(?:s|es)?(?:/|$)",
                path,
                flags=re.IGNORECASE,
            )
            if match:
                return match.group(1).lower()

            # Look for resource type in system namespace paths
            match = re.search(
                r"/system/([a-z][a-z0-9_]*?)(?:s|es)?(?:/|$)",
                path,
                flags=re.IGNORECASE,
            )
            if match:
                return match.group(1).lower()

        return ""

    def _determine_scope(self, resource_type: str) -> str:
        """Determine namespace scope for a resource type.

        Args:
            resource_type: Resource type in snake_case

        Returns:
            Scope value: "system", "shared", or "any"
        """
        if not resource_type:
            return self.default_scope

        # Check exact match first
        if resource_type in self.system_resources:
            return "system"
        if resource_type in self.shared_resources:
            return "shared"

        # Check with "views_" prefix (common in F5 XC)
        views_resource = f"views_{resource_type}"
        if views_resource in self.system_resources:
            return "system"
        if views_resource in self.shared_resources:
            return "shared"

        # Check without "views_" prefix
        if resource_type.startswith("views_"):
            base_resource = resource_type[6:]  # Remove "views_" prefix
            if base_resource in self.system_resources:
                return "system"
            if base_resource in self.shared_resources:
                return "shared"

        # Default scope for unlisted resources
        return self.default_scope

    def get_scope_for_resource(self, resource_type: str) -> str:
        """Get namespace scope for a specific resource type.

        Public method for external use (e.g., by other enrichers or tools).

        Args:
            resource_type: Resource type in snake_case

        Returns:
            Scope value: "system", "shared", or "any"
        """
        return self._determine_scope(resource_type)

    def get_stats(self) -> dict[str, Any]:
        """Get enrichment statistics.

        Returns:
            Statistics dictionary
        """
        return self.stats.to_dict()

    def reset_stats(self) -> None:
        """Reset enrichment statistics."""
        self.stats = NamespaceScopeStats()

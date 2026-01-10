# Copyright (c) 2026 Robin Mordasiewicz. MIT License.

"""Best Practices Enricher for OpenAPI specifications.

Applies domain-specific operational knowledge from config/best_practices.yaml
to OpenAPI specification info section:
- x-f5xc-best-practices: Contains common errors, security notes, and performance tips

The best practices extension helps AI assistants and CLI tools provide
contextual guidance during resource operations.

Usage:
    enricher = BestPracticesEnricher()
    spec = enricher.enrich_spec(spec, domain="virtual")
    stats = enricher.get_stats()
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .extension_constants import X_F5XC_BEST_PRACTICES, X_F5XC_CLI_DOMAIN


@dataclass
class BestPracticesEnrichmentStats:
    """Statistics from best practices enrichment."""

    specs_processed: int = 0
    best_practices_applied: int = 0
    best_practices_skipped: int = 0
    domains_with_defaults: list[str] = field(default_factory=list)
    domains_without_config: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert stats to dictionary."""
        return {
            "specs_processed": self.specs_processed,
            "best_practices_applied": self.best_practices_applied,
            "best_practices_skipped": self.best_practices_skipped,
            "domains_with_defaults": self.domains_with_defaults,
            "domains_without_config": self.domains_without_config,
        }


@dataclass
class CommonError:
    """Represents a common error scenario."""

    code: int
    message: str
    resolution: str
    prevention: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "code": self.code,
            "message": self.message,
            "resolution": self.resolution,
            "prevention": self.prevention,
        }


@dataclass
class BestPractices:
    """Domain-specific best practices."""

    common_errors: list[CommonError] = field(default_factory=list)
    security_notes: list[str] = field(default_factory=list)
    performance_tips: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for OpenAPI extension."""
        return {
            "common_errors": [e.to_dict() for e in self.common_errors],
            "security_notes": self.security_notes,
            "performance_tips": self.performance_tips,
        }

    def is_empty(self) -> bool:
        """Check if no best practices are configured."""
        return not self.common_errors and not self.security_notes and not self.performance_tips


class BestPracticesEnricher:
    """Enrich OpenAPI specifications with domain-specific best practices.

    Loads best practices from config/best_practices.yaml and applies them
    to the x-f5xc-best-practices extension in the info section.

    Best practices include:
    - common_errors: Common error scenarios with resolutions
    - security_notes: Security best practices for the domain
    - performance_tips: Performance optimization recommendations

    Attributes:
        config_path: Path to best_practices.yaml
        domains: Dictionary of domain -> BestPractices
        defaults: Default best practices for domains without config
        stats: Enrichment statistics
    """

    def __init__(self, config_path: Path | None = None) -> None:
        """Initialize enricher with best practices configuration.

        Args:
            config_path: Path to best_practices.yaml config.
                        Defaults to config/best_practices.yaml.
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "best_practices.yaml"

        self.config_path = config_path
        self.domains: dict[str, BestPractices] = {}
        self.defaults: BestPractices = BestPractices()
        self.stats = BestPracticesEnrichmentStats()
        self._config_version: str = "0.0.0"

        self._load_config()

    def _load_config(self) -> None:
        """Load best practices from YAML configuration file."""
        if not self.config_path.exists():
            # No config file - will skip enrichment gracefully
            return

        try:
            with self.config_path.open() as f:
                config = yaml.safe_load(f) or {}

            self._config_version = config.get("version", "0.0.0")

            # Load defaults
            defaults_config = config.get("defaults", {})
            self.defaults = self._parse_best_practices(defaults_config)

            # Load domain-specific best practices
            domains_config = config.get("domains", {})
            for domain_name, domain_config in domains_config.items():
                if isinstance(domain_config, dict):
                    self.domains[domain_name] = self._parse_best_practices(domain_config)

        except yaml.YAMLError:
            # Invalid YAML - skip enrichment gracefully
            pass

    def _parse_best_practices(self, config: dict[str, Any]) -> BestPractices:
        """Parse best practices from configuration dictionary.

        Args:
            config: Dictionary with common_errors, security_notes, performance_tips

        Returns:
            BestPractices dataclass
        """
        common_errors: list[CommonError] = [
            CommonError(
                code=error.get("code", 0),
                message=error.get("message", ""),
                resolution=error.get("resolution", ""),
                prevention=error.get("prevention", ""),
            )
            for error in config.get("common_errors", [])
            if isinstance(error, dict)
        ]

        return BestPractices(
            common_errors=common_errors,
            security_notes=config.get("security_notes", []),
            performance_tips=config.get("performance_tips", []),
        )

    def enrich_spec(
        self,
        spec: dict[str, Any],
        domain: str | None = None,
    ) -> dict[str, Any]:
        """Enrich OpenAPI specification with best practices.

        Applies best practices from configuration to the spec's info section
        under the x-f5xc-best-practices extension.

        Uses domain-specific best practices if available, otherwise falls
        back to defaults.

        Args:
            spec: OpenAPI specification dictionary
            domain: Domain name (e.g., "virtual"). If None, tries to extract
                   from spec's x-f5xc-cli-domain extension.

        Returns:
            Specification with enriched x-f5xc-best-practices
        """
        self.stats.specs_processed += 1

        # Determine domain from parameter or spec
        if domain is None:
            domain = self._extract_domain(spec)

        if domain is None:
            self.stats.best_practices_skipped += 1
            return spec

        # Get best practices for this domain
        best_practices = self.get_best_practices(domain)

        if best_practices is None or best_practices.is_empty():
            self.stats.best_practices_skipped += 1
            if domain not in self.stats.domains_without_config:
                self.stats.domains_without_config.append(domain)
            return spec

        # Track if we used defaults
        if domain not in self.domains and domain not in self.stats.domains_with_defaults:
            self.stats.domains_with_defaults.append(domain)

        # Ensure info section exists
        if "info" not in spec:
            spec["info"] = {}

        # Apply best practices extension
        spec["info"][X_F5XC_BEST_PRACTICES] = best_practices.to_dict()

        self.stats.best_practices_applied += 1

        return spec

    def _extract_domain(self, spec: dict[str, Any]) -> str | None:
        """Extract domain from spec's x-f5xc-cli-domain extension.

        Args:
            spec: OpenAPI specification dictionary

        Returns:
            Domain name if found, None otherwise
        """
        info = spec.get("info", {})
        return info.get(X_F5XC_CLI_DOMAIN)

    def get_best_practices(self, domain: str) -> BestPractices | None:
        """Get best practices for a domain.

        Returns domain-specific best practices if configured, otherwise
        returns defaults.

        Args:
            domain: Domain name (e.g., "virtual")

        Returns:
            BestPractices if available, None if no defaults either
        """
        if domain in self.domains:
            return self.domains[domain]

        # Fall back to defaults
        if not self.defaults.is_empty():
            return self.defaults

        return None

    def get_common_errors(self, domain: str) -> list[CommonError]:
        """Get common errors for a domain.

        Args:
            domain: Domain name (e.g., "virtual")

        Returns:
            List of common errors for the domain
        """
        best_practices = self.get_best_practices(domain)
        if best_practices:
            return best_practices.common_errors
        return []

    def get_security_notes(self, domain: str) -> list[str]:
        """Get security notes for a domain.

        Args:
            domain: Domain name (e.g., "virtual")

        Returns:
            List of security notes for the domain
        """
        best_practices = self.get_best_practices(domain)
        if best_practices:
            return best_practices.security_notes
        return []

    def get_performance_tips(self, domain: str) -> list[str]:
        """Get performance tips for a domain.

        Args:
            domain: Domain name (e.g., "virtual")

        Returns:
            List of performance tips for the domain
        """
        best_practices = self.get_best_practices(domain)
        if best_practices:
            return best_practices.performance_tips
        return []

    def has_best_practices(self, domain: str) -> bool:
        """Check if best practices exist for a domain.

        Args:
            domain: Domain name to check

        Returns:
            True if best practices are configured for the domain
        """
        return domain in self.domains

    def get_configured_domains(self) -> list[str]:
        """Get list of domains with configured best practices.

        Returns:
            Sorted list of domain names
        """
        return sorted(self.domains.keys())

    def get_config_version(self) -> str:
        """Get version of loaded best practices configuration.

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

    def enrich_index(self, index: dict[str, Any]) -> dict[str, Any]:
        """Enrich index.json with best practices summary.

        For API consistency with other enrichers. Best practices are
        applied at the spec level, so this is a pass-through.

        Args:
            index: Index dictionary to enrich

        Returns:
            Index dictionary unchanged
        """
        return index


__all__ = [
    "BestPractices",
    "BestPracticesEnricher",
    "BestPracticesEnrichmentStats",
    "CommonError",
]

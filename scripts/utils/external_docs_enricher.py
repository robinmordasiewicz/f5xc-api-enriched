"""External documentation enricher for OpenAPI specifications.

This enricher adds externalDocs metadata to OpenAPI specs,
providing direct links to F5's official documentation.

Adds the standard OpenAPI externalDocs field to the info section with:
- url: Link to relevant F5 XC documentation
- description: Brief description of the documentation

Configuration is loaded from config/external_docs.yaml.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from scripts.utils.domain_categorizer import categorize_spec

logger = logging.getLogger(__name__)


@dataclass
class ExternalDocsStats:
    """Statistics for external docs enrichment."""

    specs_enriched: int = 0
    docs_added: int = 0
    already_had_docs: int = 0
    used_default: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert stats to dictionary."""
        return {
            "specs_enriched": self.specs_enriched,
            "docs_added": self.docs_added,
            "already_had_docs": self.already_had_docs,
            "used_default": self.used_default,
            "error_count": len(self.errors),
            "errors": self.errors,
        }


class ExternalDocsEnricher:
    """Enrich OpenAPI specs with external documentation links.

    Adds standard OpenAPI externalDocs field to the spec's info section,
    providing direct links to F5's official documentation based on
    the spec's domain categorization.

    Uses config/external_docs.yaml for URL mappings.
    """

    def __init__(self, config_path: Path | None = None) -> None:
        """Initialize enricher with configuration.

        Args:
            config_path: Optional path to config file.
                        Defaults to config/external_docs.yaml
        """
        self.config_path = (
            config_path or Path(__file__).parent.parent.parent / "config" / "external_docs.yaml"
        )
        self.config: dict[str, Any] = {}
        self.domain_docs: dict[str, dict[str, str]] = {}
        self.default_docs: dict[str, str] = {}
        self.stats = ExternalDocsStats()

        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from YAML file."""
        try:
            with self.config_path.open() as f:
                self.config = yaml.safe_load(f) or {}

                # Load default documentation
                self.default_docs = self.config.get(
                    "default",
                    {
                        "url": "https://docs.cloud.f5.com/docs",
                        "description": "F5 Distributed Cloud Documentation",
                    },
                )

                # Load domain-specific documentation mappings
                domains = self.config.get("domains", {})
                for domain, doc_info in domains.items():
                    if isinstance(doc_info, dict) and "url" in doc_info:
                        self.domain_docs[domain] = {
                            "url": doc_info["url"],
                            "description": doc_info.get(
                                "description",
                                f"F5 XC Documentation - {domain}",
                            ),
                        }

                logger.info("Loaded external_docs config from %s", self.config_path)
                logger.info("Found %d domain documentation mappings", len(self.domain_docs))

        except FileNotFoundError:
            logger.warning("Configuration file not found: %s", self.config_path)
            self.config = {}
        except yaml.YAMLError:
            logger.exception("Error parsing configuration")
            self.config = {}

    def enrich_spec(
        self,
        spec: dict[str, Any],
        filename: str | None = None,
    ) -> dict[str, Any]:
        """Enrich OpenAPI specification with external documentation link.

        Adds externalDocs to the spec's info section based on
        the domain detected from the spec title or filename.

        Args:
            spec: OpenAPI specification dictionary
            filename: Optional filename for domain detection

        Returns:
            Enriched specification
        """
        try:
            info = spec.get("info", {})

            # Check if already enriched (idempotent)
            if "externalDocs" in info:
                self.stats.already_had_docs += 1
                self.stats.specs_enriched += 1
                return spec

            # Detect domain from filename or spec
            domain = self._detect_domain(spec, filename)
            external_docs = self._get_docs_for_domain(domain)

            # Add externalDocs to info section
            if "info" not in spec:
                spec["info"] = {}
            spec["info"]["externalDocs"] = external_docs

            # Update stats
            self.stats.specs_enriched += 1
            self.stats.docs_added += 1

            logger.debug(
                "Added externalDocs for domain '%s': %s",
                domain,
                external_docs["url"],
            )

        except Exception as e:
            logger.exception("Error enriching spec with external docs")
            self.stats.errors.append(
                {
                    "error": str(e),
                    "spec_title": spec.get("info", {}).get("title", "unknown"),
                    "filename": filename,
                },
            )

        return spec

    def _detect_domain(self, spec: dict[str, Any], filename: str | None = None) -> str:
        """Detect domain from filename or spec metadata.

        Uses multiple strategies to determine the domain:
        1. Use filename with DomainCategorizer if available
        2. Extract from x-ves-cli-domain extension if present
        3. Extract from spec title

        Args:
            spec: OpenAPI specification
            filename: Optional filename for categorization

        Returns:
            Detected domain name
        """
        # Strategy 1: Use filename with DomainCategorizer
        if filename:
            domain = categorize_spec(filename)
            if domain and domain != "other":
                return domain

        # Strategy 2: Use x-ves-cli-domain if present
        info = spec.get("info", {})
        cli_domain = info.get("x-ves-cli-domain")
        if cli_domain:
            return cli_domain

        # Strategy 3: Try title-based categorization
        title = info.get("title", "")
        if title:
            # Create a pseudo-filename from title for categorization
            pseudo_filename = title.lower().replace(" ", "_").replace("-", "_")
            domain = categorize_spec(pseudo_filename)
            if domain and domain != "other":
                return domain

        return "other"

    def _get_docs_for_domain(self, domain: str) -> dict[str, str]:
        """Get external docs configuration for a domain.

        Args:
            domain: Domain name

        Returns:
            Dictionary with url and description keys
        """
        if domain in self.domain_docs:
            return self.domain_docs[domain].copy()

        # Use default docs
        self.stats.used_default += 1
        return self.default_docs.copy()

    def get_docs_for_domain(self, domain: str) -> dict[str, str]:
        """Get external docs for a specific domain.

        Public method for external use (e.g., by other enrichers or tools).

        Args:
            domain: Domain name

        Returns:
            Dictionary with url and description keys
        """
        return self._get_docs_for_domain(domain)

    def get_stats(self) -> dict[str, Any]:
        """Get enrichment statistics.

        Returns:
            Statistics dictionary
        """
        return self.stats.to_dict()

    def reset_stats(self) -> None:
        """Reset enrichment statistics."""
        self.stats = ExternalDocsStats()

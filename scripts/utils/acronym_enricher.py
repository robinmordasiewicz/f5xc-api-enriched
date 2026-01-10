# Copyright (c) 2026 Robin Mordasiewicz. MIT License.

"""Acronym Enricher for OpenAPI specifications.

Applies structured technical terminology from config/acronyms.yaml
to the index.json metadata as the x-f5xc-acronyms extension.

Acronym data helps AI assistants and CLI tools provide consistent
terminology expansion for F5 Distributed Cloud APIs.

Usage:
    enricher = AcronymEnricher()
    index = enricher.enrich_index(index)
    stats = enricher.get_stats()
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class AcronymEnrichmentStats:
    """Statistics from acronym enrichment."""

    indexes_processed: int = 0
    acronyms_loaded: int = 0
    categories_loaded: int = 0
    enrichment_applied: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert stats to dictionary."""
        return {
            "indexes_processed": self.indexes_processed,
            "acronyms_loaded": self.acronyms_loaded,
            "categories_loaded": self.categories_loaded,
            "enrichment_applied": self.enrichment_applied,
        }


@dataclass
class AcronymEntry:
    """Represents a technical acronym with expansion and category."""

    acronym: str
    expansion: str
    category: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "acronym": self.acronym,
            "expansion": self.expansion,
            "category": self.category,
        }


@dataclass
class AcronymExtension:
    """Represents the complete x-f5xc-acronyms extension structure."""

    version: str = "1.0.0"
    categories: list[str] = field(default_factory=list)
    acronyms: list[AcronymEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "version": self.version,
            "categories": self.categories,
            "acronyms": [a.to_dict() for a in self.acronyms],
        }


class AcronymEnricher:
    """Enrich index.json with technical terminology definitions.

    Loads acronym data from config/acronyms.yaml and adds it to the
    x-f5xc-acronyms extension in index.json.

    Acronym extension includes:
    - Version for tracking configuration changes
    - Categories for organizing acronyms by domain
    - Structured acronym entries with expansions

    Attributes:
        config_path: Path to acronyms.yaml
        extension: AcronymExtension with all loaded data
        stats: Enrichment statistics
    """

    def __init__(self, config_path: Path | None = None) -> None:
        """Initialize enricher with acronym configuration.

        Args:
            config_path: Path to acronyms.yaml config.
                        Defaults to config/acronyms.yaml.
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "acronyms.yaml"

        self.config_path = config_path
        self.extension = AcronymExtension()
        self.stats = AcronymEnrichmentStats()

        self._load_config()

    def _load_config(self) -> None:
        """Load acronym data from YAML configuration file."""
        if not self.config_path.exists():
            # No config file - will skip enrichment gracefully
            return

        try:
            with self.config_path.open() as f:
                config = yaml.safe_load(f) or {}

            # Load extension section (structured data for x-f5xc-acronyms)
            extension_config = config.get("extension", {})
            if not extension_config:
                return

            self.extension.version = extension_config.get("version", "1.0.0")

            # Load categories
            categories = extension_config.get("categories", [])
            if isinstance(categories, list):
                self.extension.categories = categories
                self.stats.categories_loaded = len(categories)

            # Load structured acronyms
            structured_acronyms = extension_config.get("structured_acronyms", [])
            for entry in structured_acronyms:
                if isinstance(entry, dict):
                    acronym_entry = AcronymEntry(
                        acronym=entry.get("acronym", ""),
                        expansion=entry.get("expansion", ""),
                        category=entry.get("category", "Other"),
                    )
                    if acronym_entry.acronym and acronym_entry.expansion:
                        self.extension.acronyms.append(acronym_entry)
                        self.stats.acronyms_loaded += 1

        except yaml.YAMLError:
            # Invalid YAML - skip enrichment gracefully
            pass

    def enrich_index(self, index: dict[str, Any]) -> dict[str, Any]:
        """Enrich index.json with acronym terminology data.

        Adds x-f5xc-acronyms extension to index.json containing
        technical acronym definitions organized by category.

        Args:
            index: index.json dictionary

        Returns:
            Index with enriched acronym data
        """
        self.stats.indexes_processed += 1

        if not self.extension.acronyms:
            return index

        # Apply extension to index
        index["x-f5xc-acronyms"] = self.extension.to_dict()
        self.stats.enrichment_applied = True

        return index

    def get_acronym(self, acronym: str) -> AcronymEntry | None:
        """Get acronym entry by acronym string.

        Args:
            acronym: Acronym to look up (case-insensitive)

        Returns:
            AcronymEntry if found, None otherwise
        """
        acronym_upper = acronym.upper()
        for entry in self.extension.acronyms:
            if entry.acronym.upper() == acronym_upper:
                return entry
        return None

    def get_acronyms_by_category(self, category: str) -> list[AcronymEntry]:
        """Get all acronyms in a specific category.

        Args:
            category: Category name to filter by

        Returns:
            List of acronym entries in the category
        """
        return [a for a in self.extension.acronyms if a.category == category]

    def get_categories(self) -> list[str]:
        """Get all configured categories.

        Returns:
            List of category names
        """
        return self.extension.categories.copy()

    def get_all_acronyms(self) -> list[AcronymEntry]:
        """Get all configured acronyms.

        Returns:
            List of all acronym entries
        """
        return self.extension.acronyms.copy()

    def get_config_version(self) -> str:
        """Get version of loaded acronym configuration.

        Returns:
            Version string from config (e.g., "1.0.0")
        """
        return self.extension.version

    def get_stats(self) -> dict[str, Any]:
        """Get enrichment statistics.

        Returns:
            Dictionary with enrichment metrics
        """
        return self.stats.to_dict()

    def enrich_spec(
        self,
        spec: dict[str, Any],
        domain: str | None = None,  # noqa: ARG002 - API consistency with other enrichers
    ) -> dict[str, Any]:
        """Enrich OpenAPI specification with acronym data.

        For API consistency with other enrichers. Acronym enrichment is
        applied at the index level, so this is a pass-through.

        Args:
            spec: OpenAPI specification dictionary
            domain: Domain name (unused, for API consistency)

        Returns:
            Specification unchanged
        """
        return spec

    def has_acronym(self, acronym: str) -> bool:
        """Check if acronym exists in configuration.

        Args:
            acronym: Acronym to check (case-insensitive)

        Returns:
            True if acronym is configured
        """
        return self.get_acronym(acronym) is not None

    def get_expansion(self, acronym: str) -> str | None:
        """Get expansion for an acronym.

        Args:
            acronym: Acronym to expand (case-insensitive)

        Returns:
            Expansion string if found, None otherwise
        """
        entry = self.get_acronym(acronym)
        return entry.expansion if entry else None


__all__ = [
    "AcronymEnricher",
    "AcronymEnrichmentStats",
    "AcronymEntry",
    "AcronymExtension",
]

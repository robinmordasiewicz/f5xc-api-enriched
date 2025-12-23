"""Domain categorization utility for F5 XC API specifications.

This module provides centralized domain categorization patterns for categorizing
spec files by functional domain. It loads patterns from config/domain_patterns.yaml
and provides both class-based and module-level interfaces.
"""

import re
from pathlib import Path
from typing import Optional

import yaml


class DomainCategorizer:
    """Utility class for categorizing API specs by domain.

    Loads domain patterns from config/domain_patterns.yaml and provides
    efficient categorization with caching. Implements singleton pattern.
    """

    _instance: Optional["DomainCategorizer"] = None
    _patterns: dict[str, list[str]] | None = None
    _compiled_patterns: list[tuple[str, list[re.Pattern[str]]]] | None = None

    def __new__(cls) -> "DomainCategorizer":
        """Implement singleton pattern for shared instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_patterns()  # noqa: SLF001
        return cls._instance

    def _load_patterns(self) -> None:
        """Load domain patterns from YAML configuration file."""
        config_file = Path(__file__).parent.parent.parent / "config" / "domain_patterns.yaml"

        if not config_file.exists():
            raise FileNotFoundError(f"Domain patterns configuration not found: {config_file}")

        with config_file.open() as f:
            config = yaml.safe_load(f)

        if not config or "domains" not in config:
            raise ValueError("Invalid domain patterns configuration: missing 'domains' key")

        # Convert YAML structure to flat dictionary of domain -> pattern list
        self._patterns = {}
        self._compiled_patterns = []
        for domain, domain_config in config["domains"].items():
            if isinstance(domain_config, dict) and "patterns" in domain_config:
                patterns = domain_config["patterns"]
                self._patterns[domain] = patterns
                # Compile patterns at load time for performance
                try:
                    compiled = [re.compile(p) for p in patterns]
                    self._compiled_patterns.append((domain, compiled))
                except re.error as e:
                    msg = f"Invalid regex pattern in domain '{domain}': {e}"
                    raise ValueError(msg) from e
            else:
                raise ValueError(f"Invalid domain configuration for '{domain}'")

    def categorize(self, filename: str) -> str:
        """Categorize a specification filename by domain.

        Args:
            filename: Specification filename to categorize

        Returns:
            Domain name if matched, "other" if no match
        """
        if self._patterns is None or self._compiled_patterns is None:
            self._load_patterns()

        assert self._patterns is not None
        assert self._compiled_patterns is not None

        filename_lower = filename.lower()

        for domain, compiled_patterns in self._compiled_patterns:
            for pattern in compiled_patterns:
                if pattern.search(filename_lower):
                    return domain

        return "other"

    def get_domain_patterns(self) -> dict[str, list[str]]:
        """Get all domain patterns dictionary.

        Returns:
            Dictionary mapping domain names to pattern lists
        """
        if self._patterns is None:
            self._load_patterns()
        assert self._patterns is not None
        return self._patterns.copy()

    def get_all_domains(self) -> list[str]:
        """Get list of all available domains.

        Returns:
            Sorted list of domain names
        """
        if self._patterns is None:
            self._load_patterns()
        assert self._patterns is not None
        return sorted(self._patterns.keys())


# Module-level singleton instance
_categorizer = DomainCategorizer()


def categorize_spec(filename: str) -> str:
    """Categorize a specification filename by domain.

    Convenience function using the module-level singleton instance.

    Args:
        filename: Specification filename to categorize

    Returns:
        Domain name if matched, "other" if no match
    """
    return _categorizer.categorize(filename)


def get_domain_patterns() -> dict[str, list[str]]:
    """Get all domain patterns.

    Convenience function using the module-level singleton instance.

    Returns:
        Dictionary mapping domain names to pattern lists
    """
    return _categorizer.get_domain_patterns()


# Backward compatibility export: DOMAIN_PATTERNS dictionary
DOMAIN_PATTERNS = get_domain_patterns()


__all__ = [
    "DOMAIN_PATTERNS",
    "DomainCategorizer",
    "categorize_spec",
    "get_domain_patterns",
]

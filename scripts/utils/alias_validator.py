"""Domain alias validation for enriched API specifications.

Validates domain aliases for uniqueness, format compliance, and reserved word
conflicts. Used by the enrichment pipeline to ensure alias integrity across
all domains.

Alias Guidelines:
- Lowercase only: All aliases must be lowercase
- No underscores: Use hyphens for multi-word aliases (e.g., http-lb)
- Unique: No alias can conflict with another domain's name or alias
- Intuitive: Aliases should be obvious abbreviations
- Limited: 2-4 aliases per domain maximum
- Pattern: ^(?!.*-$)[a-z][a-z0-9-]{1,19}$ (2-20 chars, no trailing hyphen)
- Reserved: Cannot use CLI commands (list, get, create, delete, help, version)
"""

import re
from dataclasses import dataclass, field
from typing import Any

# Reserved words that cannot be used as aliases (CLI commands)
RESERVED_WORDS = frozenset(
    [
        "list",
        "get",
        "create",
        "delete",
        "update",
        "help",
        "version",
        "config",
        "auth",
        "login",
        "logout",
        "status",
        "info",
        "apply",
        "describe",
        "edit",
        "patch",
    ],
)

# Alias pattern: lowercase letters, numbers, hyphens; 2-20 chars
# Must start with a letter and cannot end with a hyphen
ALIAS_PATTERN = re.compile(r"^(?!.*-$)[a-z][a-z0-9-]{1,19}$")


@dataclass
class AliasValidationStats:
    """Statistics from alias validation."""

    domains_validated: int = 0
    total_aliases: int = 0
    conflicts_found: int = 0
    invalid_format: int = 0
    reserved_word_violations: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert stats to dictionary for JSON serialization."""
        return {
            "domains_validated": self.domains_validated,
            "total_aliases": self.total_aliases,
            "conflicts_found": self.conflicts_found,
            "invalid_format": self.invalid_format,
            "reserved_word_violations": self.reserved_word_violations,
            "errors": self.errors,
            "is_valid": len(self.errors) == 0,
        }


class AliasValidator:
    """Validates domain aliases for uniqueness and format compliance.

    Performs the following validations:
    1. Format validation: Aliases must match ALIAS_PATTERN
    2. Reserved word check: Aliases cannot be CLI commands
    3. Canonical name conflict: Aliases cannot match existing domain names
    4. Uniqueness check: No two domains can share the same alias
    """

    def __init__(self, domain_metadata: dict[str, dict[str, Any]]) -> None:
        """Initialize validator with domain metadata.

        Args:
            domain_metadata: Dictionary of domain names to their metadata,
                            where metadata may contain an 'aliases' list.
        """
        self.domain_metadata = domain_metadata
        self.stats = AliasValidationStats()

    def validate_all(self) -> AliasValidationStats:
        """Validate all aliases across all domains.

        Returns:
            AliasValidationStats with validation results and any errors found.
        """
        # Reset stats for fresh validation
        self.stats = AliasValidationStats()

        alias_map: dict[str, str] = {}  # alias -> domain (for uniqueness check)
        canonical_names = set(self.domain_metadata.keys())

        for domain, metadata in self.domain_metadata.items():
            self.stats.domains_validated += 1
            aliases = metadata.get("aliases", [])

            for alias in aliases:
                self.stats.total_aliases += 1

                # Check format
                if not ALIAS_PATTERN.match(alias):
                    self.stats.invalid_format += 1
                    self.stats.errors.append(
                        f"Invalid format: '{alias}' in domain '{domain}' "
                        f"(must match pattern: lowercase, 2-20 chars, no underscores)",
                    )
                    continue

                # Check reserved words
                if alias in RESERVED_WORDS:
                    self.stats.reserved_word_violations += 1
                    self.stats.errors.append(
                        f"Reserved word: '{alias}' in domain '{domain}' "
                        f"(cannot use CLI commands as aliases)",
                    )
                    continue

                # Check not a canonical domain name
                if alias in canonical_names:
                    self.stats.conflicts_found += 1
                    self.stats.errors.append(
                        f"Alias '{alias}' in domain '{domain}' "
                        f"conflicts with existing domain name '{alias}'",
                    )
                    continue

                # Check uniqueness across domains
                if alias in alias_map:
                    self.stats.conflicts_found += 1
                    self.stats.errors.append(
                        f"Duplicate alias '{alias}': used by both "
                        f"'{domain}' and '{alias_map[alias]}'",
                    )
                    continue

                # Valid alias - add to map
                alias_map[alias] = domain

        return self.stats

    def get_alias_map(self) -> dict[str, str]:
        """Get a mapping of all valid aliases to their domains.

        Returns:
            Dictionary mapping each alias to its domain name.
            Only includes aliases that passed validation.
        """
        alias_map: dict[str, str] = {}
        canonical_names = set(self.domain_metadata.keys())

        for domain, metadata in self.domain_metadata.items():
            aliases = metadata.get("aliases", [])

            for alias in aliases:
                # Only include valid aliases
                if (
                    ALIAS_PATTERN.match(alias)
                    and alias not in RESERVED_WORDS
                    and alias not in canonical_names
                    and alias not in alias_map
                ):
                    alias_map[alias] = domain

        return alias_map

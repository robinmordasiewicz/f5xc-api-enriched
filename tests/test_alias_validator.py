"""Unit tests for AliasValidator.

Tests domain alias validation for uniqueness, format compliance,
and reserved word conflicts.
"""

import pytest

from scripts.utils.alias_validator import (
    ALIAS_PATTERN,
    RESERVED_WORDS,
    AliasValidationStats,
    AliasValidator,
)
from scripts.utils.domain_metadata import DOMAIN_METADATA


class TestAliasPattern:
    """Test alias format pattern validation."""

    @pytest.mark.parametrize(
        "alias",
        [
            "lb",
            "http-lb",
            "hlb",
            "api-sec",
            "ns",
            "ce",
            "vk8s",
            "mk8s",
            "dns-zone",
        ],
    )
    def test_valid_aliases(self, alias: str) -> None:
        """Verify valid alias patterns are accepted."""
        assert ALIAS_PATTERN.match(alias)

    @pytest.mark.parametrize(
        "alias",
        [
            "LB",  # uppercase
            "Http-LB",  # mixed case
            "http_lb",  # underscore not allowed
            "1lb",  # starts with number
            "a",  # too short (min 2 chars)
            "a" * 25,  # too long (max 20 chars)
            "lb!",  # special character
            "-lb",  # starts with hyphen
            "lb-",  # could be valid pattern-wise, check format
        ],
    )
    def test_invalid_aliases(self, alias: str) -> None:
        """Verify invalid alias patterns are rejected."""
        assert not ALIAS_PATTERN.match(alias)


class TestReservedWords:
    """Test reserved word blocking."""

    @pytest.mark.parametrize(
        "word",
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
    def test_reserved_words_blocked(self, word: str) -> None:
        """Verify CLI command words are in reserved list."""
        assert word in RESERVED_WORDS


class TestAliasValidationStats:
    """Test AliasValidationStats dataclass."""

    def test_default_values(self) -> None:
        """Verify default stat values are zero."""
        stats = AliasValidationStats()
        assert stats.domains_validated == 0
        assert stats.total_aliases == 0
        assert stats.conflicts_found == 0
        assert stats.invalid_format == 0
        assert stats.reserved_word_violations == 0
        assert stats.errors == []

    def test_to_dict_contains_all_fields(self) -> None:
        """Verify to_dict includes all stat fields."""
        stats = AliasValidationStats()
        result = stats.to_dict()

        assert "domains_validated" in result
        assert "total_aliases" in result
        assert "conflicts_found" in result
        assert "invalid_format" in result
        assert "reserved_word_violations" in result
        assert "errors" in result
        assert "is_valid" in result

    def test_to_dict_is_valid_true_when_no_errors(self) -> None:
        """Verify is_valid is True when errors list is empty."""
        stats = AliasValidationStats()
        result = stats.to_dict()
        assert result["is_valid"] is True

    def test_to_dict_is_valid_false_when_errors(self) -> None:
        """Verify is_valid is False when errors list is not empty."""
        stats = AliasValidationStats()
        stats.errors.append("Test error")
        result = stats.to_dict()
        assert result["is_valid"] is False


class TestAliasValidator:
    """Test AliasValidator class."""

    def test_validates_all_domains(self) -> None:
        """Verify validator processes all domains."""
        validator = AliasValidator(DOMAIN_METADATA)
        stats = validator.validate_all()
        assert stats.domains_validated == len(DOMAIN_METADATA)

    def test_detects_duplicate_aliases(self) -> None:
        """Verify duplicate aliases across domains are detected."""
        metadata = {
            "domain1": {"aliases": ["lb"]},
            "domain2": {"aliases": ["lb"]},  # duplicate
        }
        validator = AliasValidator(metadata)
        stats = validator.validate_all()

        assert stats.conflicts_found == 1
        assert any("Duplicate alias" in error for error in stats.errors)

    def test_detects_reserved_words(self) -> None:
        """Verify reserved CLI commands are blocked as aliases."""
        metadata = {
            "domain1": {"aliases": ["list"]},  # reserved
        }
        validator = AliasValidator(metadata)
        stats = validator.validate_all()

        assert stats.reserved_word_violations == 1
        assert any("Reserved word" in error for error in stats.errors)

    def test_detects_canonical_name_conflict(self) -> None:
        """Verify aliases conflicting with domain names are detected."""
        metadata = {
            "virtual": {"aliases": ["lb"]},
            "waf": {"aliases": ["virtual"]},  # conflicts with domain name
        }
        validator = AliasValidator(metadata)
        stats = validator.validate_all()

        assert stats.conflicts_found == 1
        assert any("conflicts with existing domain name" in error for error in stats.errors)

    def test_detects_invalid_format(self) -> None:
        """Verify invalid alias formats are detected."""
        metadata = {
            "domain1": {"aliases": ["Invalid_Format"]},  # uppercase + underscore
        }
        validator = AliasValidator(metadata)
        stats = validator.validate_all()

        assert stats.invalid_format == 1
        assert any("Invalid format" in error for error in stats.errors)

    def test_handles_domains_without_aliases(self) -> None:
        """Verify domains without aliases are handled gracefully."""
        metadata = {
            "domain1": {"use_cases": ["some use case"]},  # no aliases field
            "domain2": {"aliases": []},  # empty aliases
        }
        validator = AliasValidator(metadata)
        stats = validator.validate_all()

        assert stats.domains_validated == 2
        assert stats.total_aliases == 0
        assert stats.errors == []

    def test_get_alias_map(self) -> None:
        """Verify get_alias_map returns valid alias-to-domain mapping."""
        metadata = {
            "virtual": {"aliases": ["lb", "loadbalancer"]},
            "waf": {"aliases": ["firewall"]},
        }
        validator = AliasValidator(metadata)
        alias_map = validator.get_alias_map()

        assert alias_map["lb"] == "virtual"
        assert alias_map["loadbalancer"] == "virtual"
        assert alias_map["firewall"] == "waf"

    def test_get_alias_map_excludes_invalid(self) -> None:
        """Verify get_alias_map excludes invalid aliases."""
        metadata = {
            "domain1": {"aliases": ["lb", "list"]},  # list is reserved
            "domain2": {"aliases": ["INVALID"]},  # uppercase invalid
        }
        validator = AliasValidator(metadata)
        alias_map = validator.get_alias_map()

        assert "lb" in alias_map
        assert "list" not in alias_map  # reserved
        assert "INVALID" not in alias_map  # invalid format


class TestDomainMetadataAliases:
    """Test that DOMAIN_METADATA aliases are valid and well-formed."""

    def test_all_aliases_valid(self) -> None:
        """Verify all configured aliases pass validation."""
        validator = AliasValidator(DOMAIN_METADATA)
        stats = validator.validate_all()
        assert stats.errors == [], f"Validation errors: {stats.errors}"

    def test_high_priority_domains_have_aliases(self) -> None:
        """Verify key domains have aliases configured."""
        priority_domains = [
            "virtual",
            "waf",
            "dns",
            "sites",
            "certificates",
            "network",
            "api",
            "bot_defense",
            "system",
        ]
        for domain in priority_domains:
            metadata = DOMAIN_METADATA.get(domain, {})
            aliases = metadata.get("aliases", [])
            assert len(aliases) > 0, f"Domain '{domain}' missing aliases"

    def test_aliases_follow_naming_conventions(self) -> None:
        """Verify all aliases follow lowercase hyphenated format."""
        for domain, metadata in DOMAIN_METADATA.items():
            aliases = metadata.get("aliases", [])
            for alias in aliases:
                assert alias == alias.lower(), (
                    f"Alias '{alias}' in domain '{domain}' is not lowercase"
                )
                assert "_" not in alias, f"Alias '{alias}' in domain '{domain}' contains underscore"

    def test_no_alias_exceeds_max_length(self) -> None:
        """Verify no alias exceeds 20 character limit."""
        for domain, metadata in DOMAIN_METADATA.items():
            aliases = metadata.get("aliases", [])
            for alias in aliases:
                assert len(alias) <= 20, f"Alias '{alias}' in domain '{domain}' exceeds 20 chars"

    def test_aliases_are_unique_globally(self) -> None:
        """Verify no alias is used by multiple domains."""
        seen_aliases: dict[str, str] = {}
        for domain, metadata in DOMAIN_METADATA.items():
            aliases = metadata.get("aliases", [])
            for alias in aliases:
                if alias in seen_aliases:
                    pytest.fail(
                        f"Alias '{alias}' used by both '{domain}' and '{seen_aliases[alias]}'",
                    )
                seen_aliases[alias] = domain

    def test_alias_count_reasonable(self) -> None:
        """Verify domains don't have excessive aliases (max 4 recommended)."""
        for domain, metadata in DOMAIN_METADATA.items():
            aliases = metadata.get("aliases", [])
            assert len(aliases) <= 5, (
                f"Domain '{domain}' has {len(aliases)} aliases (max 4-5 recommended)"
            )


class TestAliasValidatorIntegration:
    """Integration tests for AliasValidator with actual DOMAIN_METADATA."""

    def test_validator_is_exported(self) -> None:
        """Verify AliasValidator is exported from scripts.utils."""
        from scripts.utils import AliasValidator as ExportedValidator  # noqa: PLC0415

        assert ExportedValidator is not None
        assert ExportedValidator.__name__ == "AliasValidator"

    def test_stats_is_exported(self) -> None:
        """Verify AliasValidationStats is exported from scripts.utils."""
        from scripts.utils import AliasValidationStats as ExportedStats  # noqa: PLC0415

        assert ExportedStats is not None
        assert ExportedStats.__name__ == "AliasValidationStats"

    def test_full_validation_produces_stats(self) -> None:
        """Verify full validation produces meaningful statistics."""
        validator = AliasValidator(DOMAIN_METADATA)
        stats = validator.validate_all()

        # Should have validated all domains
        assert stats.domains_validated > 0

        # Should have found aliases (we know we added them)
        assert stats.total_aliases > 0

        # Should have no errors (we designed valid aliases)
        assert stats.errors == []

        # Verify to_dict works
        stats_dict = stats.to_dict()
        assert stats_dict["is_valid"] is True

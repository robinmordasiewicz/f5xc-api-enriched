"""Tests that validate generated domain descriptions in config/domain_descriptions.yaml.

Ensures all descriptions comply with DRY principles:
- No action verb starters (Configure, Manage, Deploy, etc.)
- No self-referencing (domain name in description)
- Character limits enforced
- Complete thoughts (end with period)
"""

from pathlib import Path
from typing import ClassVar

import pytest
import yaml

# Action verbs that should NOT start descriptions
BANNED_STARTERS = [
    "configure",
    "manage",
    "create",
    "deploy",
    "monitor",
    "access",
    "define",
    "set",
    "enable",
    "control",
    "handle",
    "automate",
    "discover",
    "build",
    "establish",
    "orchestrate",
    "implement",
    "utilize",
    "leverage",
]

# Words that should not start descriptions (articles, weak starters)
WEAK_STARTERS = [
    "this",
    "the",
    "a",
    "an",
    "provides",
    "enables",
    "offers",
    "allows",
    "supports",
]


@pytest.fixture
def domain_descriptions() -> dict:
    """Load domain descriptions from YAML.

    Returns the 'domains' dictionary directly for easier iteration.
    """
    config_path = Path(__file__).parent.parent / "config" / "domain_descriptions.yaml"
    with config_path.open() as f:
        data = yaml.safe_load(f)
        # Return the domains dict directly (excludes version/generated_at)
        return data.get("domains", {})


class TestNoActionVerbStarters:
    """Ensure no description starts with CRUD/action verbs."""

    @pytest.mark.parametrize("tier", ["short", "medium", "long"])
    def test_descriptions_are_noun_first(
        self,
        domain_descriptions: dict,
        tier: str,
    ) -> None:
        """All descriptions must start with noun/concept, not action verb."""
        violations = [
            f"{domain}.{tier}: starts with '{descs.get(tier, '').split()[0].lower().rstrip(',.:;')}'"
            for domain, descs in domain_descriptions.items()
            if descs.get(tier, "")
            and descs.get(tier, "").split()[0].lower().rstrip(",.:;") in BANNED_STARTERS
        ]

        assert not violations, "Action verb starters found:\n" + "\n".join(violations)

    @pytest.mark.parametrize("tier", ["short", "medium", "long"])
    def test_no_weak_starters(self, domain_descriptions: dict, tier: str) -> None:
        """No descriptions should start with articles or weak words."""
        violations = [
            f"{domain}.{tier}: starts with '{descs.get(tier, '').split()[0].lower().rstrip(',.:;')}'"
            for domain, descs in domain_descriptions.items()
            if descs.get(tier, "")
            and descs.get(tier, "").split()[0].lower().rstrip(",.:;") in WEAK_STARTERS
        ]

        assert not violations, "Weak starters found:\n" + "\n".join(violations)


class TestSelfReferencing:
    """Ensure descriptions don't contain full domain name."""

    # Common technical words that are allowed even if they appear in domain names
    ALLOWED_TECHNICAL_WORDS: ClassVar[set[str]] = {
        "cloud",
        "data",
        "service",
        "services",
        "network",
        "security",
        "kubernetes",
        "container",
        "billing",
        "usage",
        "threat",
        "response",
        "console",
        "admin",
        "mesh",
        "nginx",
        "object",
        "storage",
        "rate",
        "limiting",
        "statistics",
        "support",
        "users",
        "sites",
        "certificates",
    }

    @pytest.mark.parametrize("tier", ["short", "medium", "long"])
    def test_no_full_domain_name_in_description(
        self,
        domain_descriptions: dict,
        tier: str,
    ) -> None:
        """Descriptions must not contain full domain name (self-referencing)."""
        violations = []
        for domain, descs in domain_descriptions.items():
            desc = descs.get(tier, "").lower()
            if not desc:
                continue
            # Only check for FULL domain name (with underscores as spaces)
            domain_words = domain.replace("_", " ").lower()

            if domain_words in desc:
                violations.append(f"{domain}.{tier}: contains full domain name '{domain_words}'")

        assert not violations, "Self-referencing found:\n" + "\n".join(violations)


class TestCompleteness:
    """Ensure descriptions are complete thoughts."""

    @pytest.mark.parametrize("tier", ["short", "medium", "long"])
    def test_ends_with_period(self, domain_descriptions: dict, tier: str) -> None:
        """All descriptions must end with a period."""
        violations = [
            f"{domain}.{tier}: missing period"
            for domain, descs in domain_descriptions.items()
            if descs.get(tier, "").strip() and not descs.get(tier, "").strip().endswith(".")
        ]

        assert not violations, "Incomplete thoughts:\n" + "\n".join(violations)

    @pytest.mark.parametrize("tier", ["short", "medium", "long"])
    def test_no_truncation(self, domain_descriptions: dict, tier: str) -> None:
        """Descriptions must not be truncated (no ellipsis)."""
        violations = [
            f"{domain}.{tier}: truncated with ellipsis"
            for domain, descs in domain_descriptions.items()
            if "..." in descs.get(tier, "") or "…" in descs.get(tier, "")
        ]

        assert not violations, "Truncated descriptions:\n" + "\n".join(violations)


class TestCharacterLimits:
    """Ensure descriptions respect character limits."""

    def test_short_under_60_chars(self, domain_descriptions: dict) -> None:
        """Short descriptions must be under 60 characters."""
        violations = [
            f"{domain}.short: {len(descs.get('short', ''))} chars (max 60)"
            for domain, descs in domain_descriptions.items()
            if len(descs.get("short", "")) > 60
        ]

        assert not violations, "Short descriptions too long:\n" + "\n".join(violations)

    def test_medium_under_150_chars(self, domain_descriptions: dict) -> None:
        """Medium descriptions must be under 150 characters."""
        violations = [
            f"{domain}.medium: {len(descs.get('medium', ''))} chars (max 150)"
            for domain, descs in domain_descriptions.items()
            if len(descs.get("medium", "")) > 150
        ]

        assert not violations, "Medium descriptions too long:\n" + "\n".join(violations)

    def test_long_under_500_chars(self, domain_descriptions: dict) -> None:
        """Long descriptions must be under 500 characters."""
        violations = [
            f"{domain}.long: {len(descs.get('long', ''))} chars (max 500)"
            for domain, descs in domain_descriptions.items()
            if len(descs.get("long", "")) > 500
        ]

        assert not violations, "Long descriptions too long:\n" + "\n".join(violations)


class TestMinimumContent:
    """Ensure descriptions have meaningful content."""

    def test_short_has_content(self, domain_descriptions: dict) -> None:
        """Short descriptions must have at least 3 words."""
        violations = [
            f"{domain}.short: only {len(descs.get('short', '').split())} words"
            for domain, descs in domain_descriptions.items()
            if len(descs.get("short", "").split()) < 3
        ]

        assert not violations, "Short descriptions too sparse:\n" + "\n".join(
            violations,
        )

    def test_all_tiers_present(self, domain_descriptions: dict) -> None:
        """Each domain must have all three tiers defined."""
        violations = [
            f"{domain}: missing {tier} tier"
            for domain, descs in domain_descriptions.items()
            for tier in ["short", "medium", "long"]
            if tier not in descs or not descs[tier]
        ]

        assert not violations, "Missing tiers:\n" + "\n".join(violations)


class TestBannedTerms:
    """Ensure descriptions don't contain banned terms."""

    BANNED_TERMS: ClassVar[list[str]] = [
        "api",
        "endpoint",
        "specification",
        "f5",
        "volterra",
        "xc",
        "utilize",
        "leverage",
        "various",
        "multiple",
        "seamless",
        "robust",
        "powerful",
    ]

    @pytest.mark.parametrize("tier", ["short", "medium", "long"])
    def test_no_banned_terms(self, domain_descriptions: dict, tier: str) -> None:
        """Descriptions must not contain banned terms."""
        violations = []
        for domain, descs in domain_descriptions.items():
            desc = descs.get(tier, "").lower()
            violations.extend(
                f"{domain}.{tier}: contains '{term}'"
                for term in self.BANNED_TERMS
                if f" {term} " in f" {desc} " or desc.startswith(f"{term} ")
            )

        assert not violations, "Banned terms found:\n" + "\n".join(violations)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

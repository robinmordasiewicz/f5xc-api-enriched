"""Tests for the 5-layer description validation system.

Tests cover:
- Layer 1: Banned patterns (regex word boundaries)
- Layer 2: Self-referential detection
- Layer 3: Quality metrics validation
- Layer 4: Circular definition detection
- Layer 5: Full check_dry_compliance integration
"""

import pytest

from scripts.generate_descriptions import (
    BANNED_PATTERNS,
    check_banned_patterns,
    check_dry_compliance,
    is_circular_definition,
    is_self_referential,
    validate_quality_metrics,
)


class TestBannedPatterns:
    """Layer 1: Test regex-based banned pattern detection."""

    @pytest.mark.parametrize(
        ("text", "should_fail"),
        [
            # Redundant terms
            ("This is the API for users", True),
            ("REST API documentation", True),
            ("endpoint configuration", True),
            ("specifications for the service", True),
            # Word boundary test - should NOT fail
            ("rapid deployment", False),
            ("therapy management", False),
            ("rapier tools", False),
            # Brand names
            ("F5 load balancer", True),
            ("XC configuration", True),
            ("Distributed Cloud services", True),
            ("Volterra platform", True),
            # Filler words
            ("utilize advanced features", True),
            ("leverage cloud services", True),
            ("facilitate communication", True),
            ("in order to configure", True),
            # Acceptable alternatives
            ("use advanced features", False),
            ("enable communication", False),
            ("to configure settings", False),
            # Vague descriptors
            ("various configurations", True),
            ("multiple options available", True),
            ("several settings etc.", True),
            # Marketing hype
            ("seamless integration", True),
            ("robust security", True),
            ("powerful automation", True),
            ("cutting-edge technology", True),
            # Passive voice
            ("Data is returned by the server", True),
            ("Connections are handled automatically", True),
            # Active voice (should pass)
            ("Returns data from the server", False),
            ("Handles connections automatically", False),
            # Truncation indicators
            ("Configure settings...", True),
            ("Set up load balancing…", True),
        ],
    )
    def test_banned_patterns(self, text: str, should_fail: bool) -> None:
        """Test that banned patterns are correctly detected."""
        violations = check_banned_patterns("short", text)
        if should_fail:
            assert len(violations) > 0, f"Expected violation for: {text}"
        else:
            assert len(violations) == 0, f"Unexpected violation for: {text}"

    def test_patterns_are_case_insensitive(self) -> None:
        """Verify all patterns match case-insensitively."""
        # Test various cases
        test_cases = [
            "API configuration",
            "api configuration",
            "Api Configuration",
            "API CONFIGURATION",
        ]
        for text in test_cases:
            violations = check_banned_patterns("short", text)
            assert len(violations) > 0, f"Should detect API in: {text}"

    def test_word_boundaries_prevent_false_positives(self) -> None:
        """Verify word boundaries prevent matching within words."""
        # These should NOT trigger violations
        safe_texts = [
            "rapid deployment",  # Contains "api" but not as word
            "therapy management",  # Contains "api" substring
            "capitalize on opportunities",  # Contains "api" substring
        ]
        for text in safe_texts:
            violations = check_banned_patterns("short", text)
            api_violations = [v for v in violations if "api" in v.lower()]
            assert len(api_violations) == 0, f"False positive for: {text}"


class TestSelfReferential:
    """Layer 2: Test self-referential pattern detection."""

    @pytest.mark.parametrize(
        ("domain", "description", "should_fail"),
        [
            # Exact match patterns
            ("authentication", "Authentication API", True),
            ("data_intelligence", "Data Intelligence Service", True),
            ("virtual", "Virtual APIs", True),
            ("network_security", "Network Security System", True),
            # Acceptable descriptions
            ("authentication", "Secure identity verification", False),
            ("data_intelligence", "Analyze traffic patterns", False),
            ("virtual", "Configure load balancers", False),
        ],
    )
    def test_self_referential_detection(
        self,
        domain: str,
        description: str,
        should_fail: bool,
    ) -> None:
        """Test detection of domain name + generic suffix patterns."""
        is_violation, msg = is_self_referential(domain, description)
        if should_fail:
            assert is_violation, f"Expected violation for: {domain} -> {description}"
            assert "LAZY" in msg
        else:
            assert not is_violation, f"Unexpected violation for: {domain} -> {description}"


class TestQualityMetrics:
    """Layer 3: Test quality metrics validation."""

    def test_short_description_character_limit(self) -> None:
        """Verify short descriptions are limited to 60 characters."""
        long_text = "A" * 65
        errors = validate_quality_metrics(long_text, "short")
        assert any("LENGTH" in e or "exceeds" in e.lower() for e in errors)

    def test_medium_description_character_limit(self) -> None:
        """Verify medium descriptions are limited to 150 characters."""
        long_text = "A" * 155
        errors = validate_quality_metrics(long_text, "medium")
        assert any("LENGTH" in e or "exceeds" in e.lower() for e in errors)

    def test_long_description_character_limit(self) -> None:
        """Verify long descriptions are limited to 500 characters."""
        long_text = "A" * 505
        errors = validate_quality_metrics(long_text, "long")
        assert any("LENGTH" in e or "exceeds" in e.lower() for e in errors)

    def test_minimum_word_count(self) -> None:
        """Verify descriptions have at least 3 words."""
        errors = validate_quality_metrics("Too short", "short")
        assert any("SPARSE" in e for e in errors)

    @pytest.mark.parametrize(
        ("first_word", "should_pass"),
        [
            ("Configure", True),
            ("Manage", True),
            ("Deploy", True),
            ("Create", True),
            ("Monitor", True),
            ("Discover", True),
            ("Connect", True),
            ("Access", True),
            ("This", False),
            ("The", False),
            ("A", False),
            ("Provides", False),
        ],
    )
    def test_action_verb_requirement(self, first_word: str, should_pass: bool) -> None:
        """Verify short descriptions must start with action verbs."""
        text = f"{first_word} load balancers and routing"
        errors = validate_quality_metrics(text, "short")
        style_errors = [e for e in errors if "STYLE" in e]
        if should_pass:
            assert len(style_errors) == 0, f"Unexpected style error for: {first_word}"
        else:
            assert len(style_errors) > 0, f"Expected style error for: {first_word}"


class TestCircularDefinition:
    """Layer 4: Test circular definition detection."""

    def test_short_description_no_repetition(self) -> None:
        """Short descriptions should not repeat exact same words."""
        # "routes" and "route" are different words, so no violation
        is_circular, _ = is_circular_definition("Manage routes and route tables", "short")
        assert not is_circular, "Different word forms should not trigger violation"

        # Same word repeated should trigger violation
        is_circular, _ = is_circular_definition("Manage security and security policies", "short")
        assert is_circular, "Should detect 'security' repetition in short"

    def test_medium_description_no_repetition(self) -> None:
        """Medium descriptions should not repeat words."""
        is_circular, _ = is_circular_definition(
            "Configure security settings and security policies",
            "medium",
        )
        assert is_circular, "Should detect 'security' repetition in medium"

    def test_long_description_allows_some_repetition(self) -> None:
        """Long descriptions allow up to 2 repetitions of a word."""
        # 2 repetitions should pass
        is_circular, _ = is_circular_definition(
            "Configure cache rules for caching behavior",
            "long",
        )
        assert not is_circular, "Should allow 2 repetitions in long"

        # 3+ repetitions should fail
        is_circular, _ = is_circular_definition(
            "Configure cache rules for cache invalidation and cache purging",
            "long",
        )
        assert is_circular, "Should detect 3+ repetitions in long"

    def test_short_words_ignored(self) -> None:
        """Words with 4 or fewer characters should be ignored."""
        is_circular, _ = is_circular_definition("Set the API and the DNS", "short")
        # "the" appears twice but should be ignored (≤4 chars)
        # "API" triggers banned pattern, not circular
        assert not is_circular, "Should ignore short words"


class TestCheckDryCompliance:
    """Layer 5: Integration test for complete validation."""

    def test_valid_descriptions_pass(self) -> None:
        """Verify well-formed descriptions pass all checks."""
        descriptions = {
            "short": "Configure load balancers and routing",
            "medium": "Create HTTP and TCP listeners with health checks. Define failover policies.",
            "long": (
                "Deploy application delivery infrastructure with origin pools. "
                "Set up geo-routing, rate limiting, and SSL termination. "
                "Integrate with security policies for WAF and bot protection."
            ),
        }
        violations = check_dry_compliance("virtual", descriptions)
        assert len(violations) == 0, f"Unexpected violations: {violations}"

    def test_api_in_description_fails(self) -> None:
        """Verify 'API' in description triggers violation."""
        descriptions = {
            "short": "Authentication API",
            "medium": "Configure authentication.",
            "long": "Set up identity verification.",
        }
        violations = check_dry_compliance("authentication", descriptions)
        assert any("REDUNDANT" in v and "API" in v for v in violations)

    def test_domain_name_in_description_fails(self) -> None:
        """Verify domain name in description triggers violation."""
        descriptions = {
            "short": "Manage virtual resources",
            "medium": "Configure virtual machines.",
            "long": "Deploy virtual infrastructure.",
        }
        violations = check_dry_compliance("virtual", descriptions)
        assert any("domain name" in v.lower() for v in violations)

    def test_brand_names_fail(self) -> None:
        """Verify brand names trigger violations."""
        descriptions = {
            "short": "Configure F5 services",
            "medium": "Manage XC deployments.",
            "long": "Set up Distributed Cloud infrastructure.",
        }
        violations = check_dry_compliance("network", descriptions)
        assert any("BRAND" in v for v in violations)

    def test_cross_tier_repetition_detection(self) -> None:
        """Verify excessive word overlap between tiers is detected.

        Cross-tier overlap requires 4+ significant words to trigger.
        Uses unusual domain words that are NOT in the stop words list.
        Common terms like 'security', 'policies', 'rules' are filtered out.
        """
        descriptions = {
            # Use words NOT in the stop_words list: kubernetes, container, replica, upstream, downstream
            # These are significant domain-specific words that should trigger overlap detection
            "short": "Orchestrate kubernetes replica upstream downstream",
            "medium": "Orchestrate kubernetes replica upstream downstream clusters. Synchronize stateful workloads.",
            "long": "Orchestrate kubernetes replica upstream downstream clusters. Synchronize stateful workloads across regions. Maintain replica consistency.",
        }
        violations = check_dry_compliance("orchestration", descriptions)
        # Should detect significant overlap (4+ words: kubernetes, replica, upstream, downstream)
        assert any("Repetition" in v or "overlap" in v.lower() for v in violations)


class TestBannedPatternsCompleteness:
    """Test that BANNED_PATTERNS covers all required categories."""

    def test_redundant_category_exists(self) -> None:
        """Verify redundant terms are covered."""
        patterns_str = str(BANNED_PATTERNS)
        assert "api" in patterns_str.lower()
        assert "endpoint" in patterns_str.lower()

    def test_brand_category_exists(self) -> None:
        """Verify brand names are covered."""
        patterns_str = str(BANNED_PATTERNS)
        assert "f5" in patterns_str.lower()
        assert "volterra" in patterns_str.lower()

    def test_filler_category_exists(self) -> None:
        """Verify filler words are covered."""
        patterns_str = str(BANNED_PATTERNS)
        assert "utilize" in patterns_str.lower()
        assert "leverage" in patterns_str.lower()

    def test_vague_category_exists(self) -> None:
        """Verify vague descriptors are covered."""
        patterns_str = str(BANNED_PATTERNS)
        assert "various" in patterns_str.lower()
        assert "etc" in patterns_str.lower()

    def test_marketing_category_exists(self) -> None:
        """Verify marketing hype is covered."""
        patterns_str = str(BANNED_PATTERNS)
        assert "seamless" in patterns_str.lower()
        assert "robust" in patterns_str.lower()

    def test_passive_voice_category_exists(self) -> None:
        """Verify passive voice patterns are covered."""
        patterns_str = str(BANNED_PATTERNS)
        assert "is returned" in patterns_str.lower()
        assert "are handled" in patterns_str.lower()

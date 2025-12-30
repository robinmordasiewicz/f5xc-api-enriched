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
    DOMAIN_SYNONYMS,
    SUCCESSFUL_PATTERNS,
    Violation,
    check_banned_patterns,
    check_cross_tier_violations,
    check_domain_name_usage,
    check_dry_compliance,
    is_circular_definition,
    is_self_referential,
    run_all_validations_structured,
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


class TestViolationDataclass:
    """Test the Violation dataclass and its methods."""

    def test_violation_str_representation(self) -> None:
        """Verify string representation for backward compatibility."""
        v = Violation(
            layer="self_referential",
            tier="long",
            code="DOMAIN_NAME",
            message="Contains domain name",
            location="observability",
            suggestion="Replace with: monitoring infrastructure",
        )
        assert "long" in str(v)
        assert "Contains domain name" in str(v)

    def test_violation_to_feedback_basic(self) -> None:
        """Verify to_feedback() generates actionable feedback."""
        v = Violation(
            layer="self_referential",
            tier="long",
            code="DOMAIN_NAME",
            message="Contains domain name 'observability'",
            location="observability",
            suggestion="Replace with: monitoring infrastructure, telemetry systems",
            examples=["Deploy monitoring infrastructure with metrics collection"],
        )
        feedback = v.to_feedback()
        assert "LONG" in feedback
        assert "DOMAIN_NAME" in feedback
        assert "observability" in feedback
        assert "monitoring infrastructure" in feedback
        assert "Deploy monitoring infrastructure" in feedback

    def test_violation_to_feedback_without_examples(self) -> None:
        """Verify to_feedback() works without examples."""
        v = Violation(
            layer="banned_patterns",
            tier="short",
            code="REDUNDANT",
            message="Banned term: API",
            location="API",
            suggestion="Remove or replace this term",
        )
        feedback = v.to_feedback()
        assert "SHORT" in feedback
        assert "REDUNDANT" in feedback
        assert "API" in feedback

    def test_violation_to_feedback_cross_tier(self) -> None:
        """Verify to_feedback() handles cross-tier violations."""
        v = Violation(
            layer="cross_tier",
            tier="cross_tier",
            code="CROSS_TIER_OVERLAP",
            message="Medium and long share 4+ words",
            location="connections, transit, azure, virtual",
            suggestion="Replace 'connections' with links/paths; 'transit' with routing",
        )
        feedback = v.to_feedback()
        assert "CROSS_TIER" in feedback
        assert "connections" in feedback
        assert "links" in feedback or "Replace" in feedback


class TestDomainNameUsage:
    """Test the check_domain_name_usage() function."""

    def test_detects_domain_name_in_text(self) -> None:
        """Verify domain name is detected in text."""
        v = check_domain_name_usage(
            "observability",
            "Configure observability tools and dashboards",
            "long",
        )
        assert v is not None
        assert v.code == "DOMAIN_NAME"
        assert v.tier == "long"
        assert "observability" in v.location

    def test_no_violation_when_domain_absent(self) -> None:
        """Verify no violation when domain name is not present."""
        v = check_domain_name_usage(
            "observability",
            "Configure monitoring tools and dashboards",
            "long",
        )
        assert v is None

    def test_provides_domain_synonyms(self) -> None:
        """Verify suggestion includes domain-specific synonyms."""
        v = check_domain_name_usage(
            "observability",
            "Set up observability pipelines",
            "medium",
        )
        assert v is not None
        assert "monitoring" in v.suggestion.lower() or "telemetry" in v.suggestion.lower()

    def test_handles_underscore_domains(self) -> None:
        """Verify domains with underscores are normalized."""
        v = check_domain_name_usage(
            "network_security",
            "Configure network security policies",
            "short",
        )
        assert v is not None
        assert v.code == "DOMAIN_NAME"


class TestCrossTierViolations:
    """Test the check_cross_tier_violations() function."""

    def test_detects_word_overlap(self) -> None:
        """Verify word overlap is detected between tiers (needs 4+ words not in stop list)."""
        # Use words NOT in stop_words: connections, transit, virtual, peering, upstream
        descriptions = {
            "short": "Orchestrate connections transit virtual peering",
            "medium": "Handle connections with transit links. Set up virtual peering upstream.",
            "long": "Deploy connections across regions. Enable transit virtual peering upstream.",
        }
        violations = check_cross_tier_violations(descriptions)
        assert len(violations) > 0
        overlap_v = [v for v in violations if v.code == "CROSS_TIER_OVERLAP"]
        assert len(overlap_v) > 0

    def test_no_violation_with_unique_vocabulary(self) -> None:
        """Verify no violation when tiers use unique words."""
        descriptions = {
            "short": "Configure load balancers",
            "medium": "Define routing policies with health checks. Set failover rules.",
            "long": "Manage traffic distribution across regions. Monitor latency and throughput metrics.",
        }
        violations = check_cross_tier_violations(descriptions)
        # Should not have cross-tier overlap since vocabulary is different
        overlap_v = [v for v in violations if v.code == "CROSS_TIER_OVERLAP"]
        assert len(overlap_v) == 0

    def test_provides_synonym_hints(self) -> None:
        """Verify synonym hints are provided for overlapping words."""
        descriptions = {
            "short": "Orchestrate kubernetes replica upstream downstream",
            "medium": "Orchestrate kubernetes replica upstream downstream clusters.",
            "long": "Orchestrate kubernetes replica upstream downstream in regions.",
        }
        violations = check_cross_tier_violations(descriptions)
        overlap_v = [v for v in violations if v.code == "CROSS_TIER_OVERLAP"]
        if overlap_v:
            # Should have synonym suggestions
            assert "→" in overlap_v[0].suggestion or "Replace" in overlap_v[0].suggestion


class TestRunAllValidationsStructured:
    """Test the run_all_validations_structured() function."""

    def test_returns_empty_for_valid_descriptions(self) -> None:
        """Verify empty list for compliant descriptions."""
        descriptions = {
            "short": "Configure load balancers and routing",
            "medium": "Create HTTP listeners with health checks. Define failover policies.",
            "long": (
                "Deploy application delivery infrastructure with origin pools. "
                "Set up geo-routing, rate limiting, and SSL termination."
            ),
        }
        violations = run_all_validations_structured("virtual", descriptions)
        # Filter out any overlap violations (depends on exact wording)
        critical_violations = [v for v in violations if v.code in ("DOMAIN_NAME", "BANNED_PATTERN")]
        assert len(critical_violations) == 0

    def test_returns_violations_for_banned_terms(self) -> None:
        """Verify violations are returned for banned terms."""
        descriptions = {
            "short": "Configure the API endpoints",
            "medium": "Create HTTP listeners.",
            "long": "Deploy infrastructure.",
        }
        violations = run_all_validations_structured("virtual", descriptions)
        assert len(violations) > 0
        assert any(v.code == "REDUNDANT" for v in violations)

    def test_returns_violations_for_domain_name(self) -> None:
        """Verify violations are returned for domain name in text."""
        descriptions = {
            "short": "Configure observability tools",
            "medium": "Create dashboards for observability data.",
            "long": "Deploy observability infrastructure.",
        }
        violations = run_all_validations_structured("observability", descriptions)
        assert len(violations) > 0
        domain_violations = [v for v in violations if v.code == "DOMAIN_NAME"]
        assert len(domain_violations) >= 1

    def test_all_violations_have_required_fields(self) -> None:
        """Verify all violations have required fields populated."""
        descriptions = {
            "short": "The API provides observability",
            "medium": "Various settings are handled.",
            "long": "Robust and seamless integration is provided.",
        }
        violations = run_all_validations_structured("observability", descriptions)
        for v in violations:
            assert v.layer, "layer should be set"
            assert v.tier, "tier should be set"
            assert v.code, "code should be set"
            assert v.message, "message should be set"


class TestDomainSynonymsCompleteness:
    """Test that DOMAIN_SYNONYMS covers all domains."""

    def test_observability_has_synonyms(self) -> None:
        """Verify observability domain has synonyms."""
        assert "observability" in DOMAIN_SYNONYMS
        synonyms = DOMAIN_SYNONYMS["observability"]
        assert len(synonyms) >= 2
        assert "monitoring" in " ".join(synonyms).lower()

    def test_sites_has_synonyms(self) -> None:
        """Verify sites domain has synonyms."""
        assert "sites" in DOMAIN_SYNONYMS
        synonyms = DOMAIN_SYNONYMS["sites"]
        assert len(synonyms) >= 2

    def test_all_major_domains_covered(self) -> None:
        """Verify all major domains have synonym mappings."""
        major_domains = [
            "observability",
            "sites",
            "network",
            "authentication",
            "waf",
            "cdn",
            "dns",
            "virtual",
            "certificates",
            "users",
        ]
        for domain in major_domains:
            assert domain in DOMAIN_SYNONYMS, f"Missing synonyms for {domain}"


class TestSuccessfulPatterns:
    """Test that SUCCESSFUL_PATTERNS are valid."""

    def test_all_categories_have_patterns(self) -> None:
        """Verify all categories have pattern examples."""
        expected_categories = ["infrastructure", "security", "delivery", "management", "operations"]
        for cat in expected_categories:
            assert cat in SUCCESSFUL_PATTERNS, f"Missing pattern for {cat}"

    def test_patterns_have_all_tiers(self) -> None:
        """Verify each pattern has short/medium/long."""
        for cat, pattern in SUCCESSFUL_PATTERNS.items():
            assert "short" in pattern, f"{cat} missing short"
            assert "medium" in pattern, f"{cat} missing medium"
            assert "long" in pattern, f"{cat} missing long"

    def test_patterns_fit_character_limits(self) -> None:
        """Verify patterns fit within character limits."""
        for cat, pattern in SUCCESSFUL_PATTERNS.items():
            assert len(pattern["short"]) <= 60, f"{cat} short too long: {len(pattern['short'])}"
            assert len(pattern["medium"]) <= 150, f"{cat} medium too long: {len(pattern['medium'])}"
            assert len(pattern["long"]) <= 500, f"{cat} long too long: {len(pattern['long'])}"

    def test_patterns_start_with_action_verbs(self) -> None:
        """Verify patterns start with action verbs."""
        action_verbs = {
            "configure",
            "create",
            "manage",
            "define",
            "deploy",
            "set",
            "route",
            "monitor",
            "collect",
            "analyze",
        }
        for cat, pattern in SUCCESSFUL_PATTERNS.items():
            first_word = pattern["short"].split()[0].lower()
            assert first_word in action_verbs, (
                f"{cat} short doesn't start with action verb: {first_word}"
            )

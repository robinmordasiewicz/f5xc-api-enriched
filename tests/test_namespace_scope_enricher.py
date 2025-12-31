"""Tests for NamespaceScopeEnricher.

Tests the enrichment of OpenAPI specs with namespace scope metadata
indicating which namespaces each resource type can be created in.
"""

import pytest

from scripts.utils.namespace_scope_enricher import (
    NamespaceScopeEnricher,
    NamespaceScopeStats,
)


class TestNamespaceScopeStats:
    """Test NamespaceScopeStats dataclass."""

    def test_stats_initialization(self):
        """Test stats initialization with default values."""
        stats = NamespaceScopeStats()
        assert stats.specs_enriched == 0
        assert stats.system_scoped == 0
        assert stats.shared_scoped == 0
        assert stats.any_scoped == 0
        assert stats.already_had_scope == 0
        assert stats.errors == []

    def test_stats_to_dict(self):
        """Test stats conversion to dictionary."""
        stats = NamespaceScopeStats()
        stats.specs_enriched = 5
        stats.system_scoped = 2
        stats.shared_scoped = 1
        stats.any_scoped = 2

        result = stats.to_dict()
        assert result["specs_enriched"] == 5
        assert result["system_scoped"] == 2
        assert result["shared_scoped"] == 1
        assert result["any_scoped"] == 2
        assert "error_count" in result


class TestNamespaceScopeEnricherBasics:
    """Test basic NamespaceScopeEnricher functionality."""

    def test_enricher_initialization(self):
        """Test enricher initializes with config loaded."""
        enricher = NamespaceScopeEnricher()
        assert enricher.config is not None
        assert enricher.extension_name == "x-ves-namespace-scope"
        assert enricher.default_scope == "any"
        assert enricher.stats is not None

    def test_resources_loaded(self):
        """Test that system and shared resources are loaded."""
        enricher = NamespaceScopeEnricher()
        # Should have system resources
        assert len(enricher.system_resources) > 0
        # Should have shared resources
        assert len(enricher.shared_resources) > 0
        # Known system resources
        assert "alert_policy" in enricher.system_resources
        assert "aws_vpc_site" in enricher.system_resources
        assert "namespace" in enricher.system_resources
        # Known shared resource
        assert "namespace_role_binding" in enricher.shared_resources

    def test_get_stats(self):
        """Test get_stats returns valid dictionary."""
        enricher = NamespaceScopeEnricher()
        stats = enricher.get_stats()
        assert isinstance(stats, dict)
        assert "specs_enriched" in stats
        assert "system_scoped" in stats
        assert "shared_scoped" in stats
        assert "any_scoped" in stats

    def test_reset_stats(self):
        """Test reset_stats clears statistics."""
        enricher = NamespaceScopeEnricher()
        enricher.stats.specs_enriched = 10
        enricher.stats.system_scoped = 5
        enricher.reset_stats()
        assert enricher.stats.specs_enriched == 0
        assert enricher.stats.system_scoped == 0


class TestScopeDetermination:
    """Test scope determination logic."""

    def test_system_scope_exact_match(self):
        """Test system scope for exact resource match."""
        enricher = NamespaceScopeEnricher()
        assert enricher._determine_scope("alert_policy") == "system"
        assert enricher._determine_scope("aws_vpc_site") == "system"
        assert enricher._determine_scope("fleet") == "system"
        assert enricher._determine_scope("namespace") == "system"

    def test_shared_scope_exact_match(self):
        """Test shared scope for exact resource match."""
        enricher = NamespaceScopeEnricher()
        assert enricher._determine_scope("namespace_role_binding") == "shared"

    def test_any_scope_for_unlisted(self):
        """Test any scope for unlisted resources."""
        enricher = NamespaceScopeEnricher()
        assert enricher._determine_scope("http_loadbalancer") == "any"
        assert enricher._determine_scope("origin_pool") == "any"
        assert enricher._determine_scope("waf") == "any"
        assert enricher._determine_scope("unknown_resource") == "any"

    def test_scope_with_views_prefix(self):
        """Test scope detection for views_ prefixed resources."""
        enricher = NamespaceScopeEnricher()
        # views_aws_vpc_site should match aws_vpc_site scope
        assert enricher._determine_scope("views_aws_vpc_site") == "system"
        assert enricher._determine_scope("views_voltstack_site") == "system"

    def test_empty_resource_type_returns_default(self):
        """Test empty resource type returns default scope."""
        enricher = NamespaceScopeEnricher()
        assert enricher._determine_scope("") == "any"

    def test_get_scope_for_resource_public_method(self):
        """Test public get_scope_for_resource method."""
        enricher = NamespaceScopeEnricher()
        assert enricher.get_scope_for_resource("alert_policy") == "system"
        assert enricher.get_scope_for_resource("namespace_role_binding") == "shared"
        assert enricher.get_scope_for_resource("http_loadbalancer") == "any"


class TestResourceTypeExtraction:
    """Test resource type extraction from specs."""

    def test_extract_from_title_basic(self):
        """Test extracting resource type from basic title."""
        enricher = NamespaceScopeEnricher()
        assert enricher._extract_resource_from_title("Alert Policy API") == "alert_policy"
        assert enricher._extract_resource_from_title("Fleet API") == "fleet"

    def test_extract_from_title_multi_word(self):
        """Test extracting resource type from multi-word title."""
        enricher = NamespaceScopeEnricher()
        assert enricher._extract_resource_from_title("AWS VPC Site API") == "aws_vpc_site"
        assert (
            enricher._extract_resource_from_title("HTTP Load Balancer API") == "http_load_balancer"
        )

    def test_extract_from_title_camel_case(self):
        """Test extracting resource type from camelCase title."""
        enricher = NamespaceScopeEnricher()
        result = enricher._extract_resource_from_title("HttpLoadBalancer API")
        assert "http" in result.lower()
        assert "load" in result.lower() or "loadbalancer" in result.lower()

    def test_extract_from_paths_namespace_pattern(self):
        """Test extracting resource type from path patterns."""
        enricher = NamespaceScopeEnricher()
        paths = {
            "/api/config/namespaces/{namespace}/alert_policys": {},
            "/api/config/namespaces/{namespace}/alert_policys/{name}": {},
        }
        assert enricher._extract_resource_from_paths(paths) == "alert_policy"

    def test_extract_from_paths_system_pattern(self):
        """Test extracting resource type from system namespace paths."""
        enricher = NamespaceScopeEnricher()
        paths = {
            "/api/config/system/fleets": {},
            "/api/config/system/fleets/{name}": {},
        }
        assert enricher._extract_resource_from_paths(paths) == "fleet"

    def test_extract_from_paths_empty(self):
        """Test empty paths returns empty string."""
        enricher = NamespaceScopeEnricher()
        assert enricher._extract_resource_from_paths({}) == ""


class TestSpecEnrichment:
    """Test specification enrichment."""

    def test_enrich_spec_adds_extension(self):
        """Test that enrich_spec adds the namespace scope extension."""
        enricher = NamespaceScopeEnricher()
        spec = {
            "info": {
                "title": "Alert Policy API",
            },
            "paths": {},
        }
        result = enricher.enrich_spec(spec)
        assert "x-ves-namespace-scope" in result["info"]
        assert result["info"]["x-ves-namespace-scope"] == "system"

    def test_enrich_spec_system_resource(self):
        """Test enrichment of system-scoped resource."""
        enricher = NamespaceScopeEnricher()
        spec = {
            "info": {
                "title": "AWS VPC Site API",
            },
            "paths": {
                "/api/config/namespaces/{namespace}/aws_vpc_sites": {},
            },
        }
        result = enricher.enrich_spec(spec)
        assert result["info"]["x-ves-namespace-scope"] == "system"
        assert enricher.stats.system_scoped == 1

    def test_enrich_spec_shared_resource(self):
        """Test enrichment of shared-scoped resource."""
        enricher = NamespaceScopeEnricher()
        spec = {
            "info": {
                "title": "Namespace Role Binding API",
            },
            "paths": {},
        }
        result = enricher.enrich_spec(spec)
        assert result["info"]["x-ves-namespace-scope"] == "shared"
        assert enricher.stats.shared_scoped == 1

    def test_enrich_spec_any_resource(self):
        """Test enrichment of any-scoped resource."""
        enricher = NamespaceScopeEnricher()
        spec = {
            "info": {
                "title": "HTTP Load Balancer API",
            },
            "paths": {},
        }
        result = enricher.enrich_spec(spec)
        assert result["info"]["x-ves-namespace-scope"] == "any"
        assert enricher.stats.any_scoped == 1

    def test_enrich_spec_idempotent(self):
        """Test that enrichment is idempotent."""
        enricher = NamespaceScopeEnricher()
        spec = {
            "info": {
                "title": "Alert Policy API",
                "x-ves-namespace-scope": "system",  # Already set
            },
            "paths": {},
        }
        result = enricher.enrich_spec(spec)
        assert result["info"]["x-ves-namespace-scope"] == "system"
        assert enricher.stats.already_had_scope == 1

    def test_enrich_spec_preserves_existing_info(self):
        """Test that enrichment preserves existing info fields."""
        enricher = NamespaceScopeEnricher()
        spec = {
            "info": {
                "title": "Alert Policy API",
                "version": "1.0.0",
                "description": "Alert policy management",
            },
            "paths": {},
        }
        result = enricher.enrich_spec(spec)
        assert result["info"]["title"] == "Alert Policy API"
        assert result["info"]["version"] == "1.0.0"
        assert result["info"]["description"] == "Alert policy management"
        assert "x-ves-namespace-scope" in result["info"]

    def test_enrich_spec_creates_info_if_missing(self):
        """Test that enrichment creates info section if missing."""
        enricher = NamespaceScopeEnricher()
        spec = {
            "paths": {},
        }
        result = enricher.enrich_spec(spec)
        assert "info" in result
        assert "x-ves-namespace-scope" in result["info"]

    def test_enrich_spec_stats_updated(self):
        """Test that stats are updated after enrichment."""
        enricher = NamespaceScopeEnricher()
        spec = {
            "info": {
                "title": "Fleet API",
            },
            "paths": {},
        }
        enricher.enrich_spec(spec)
        assert enricher.stats.specs_enriched == 1

    def test_enrich_multiple_specs(self):
        """Test enriching multiple specifications."""
        enricher = NamespaceScopeEnricher()
        specs = [
            {"info": {"title": "Alert Policy API"}, "paths": {}},  # system
            {"info": {"title": "Namespace Role Binding API"}, "paths": {}},  # shared
            {"info": {"title": "HTTP Load Balancer API"}, "paths": {}},  # any
        ]
        for spec in specs:
            enricher.enrich_spec(spec)
        assert enricher.stats.specs_enriched == 3
        assert enricher.stats.system_scoped == 1
        assert enricher.stats.shared_scoped == 1
        assert enricher.stats.any_scoped == 1


class TestResourceTypeDetection:
    """Test detect_resource_type method."""

    def test_detect_from_title(self):
        """Test resource type detection from title."""
        enricher = NamespaceScopeEnricher()
        spec = {
            "info": {"title": "Alert Policy API"},
            "paths": {},
        }
        result = enricher._detect_resource_type(spec)
        assert result == "alert_policy"

    def test_detect_from_paths(self):
        """Test resource type detection from paths when title extraction fails."""
        enricher = NamespaceScopeEnricher()
        spec = {
            "info": {"title": ""},  # Empty title to fall through to paths
            "paths": {
                "/api/config/namespaces/{namespace}/alert_policys": {},
            },
        }
        result = enricher._detect_resource_type(spec)
        assert result == "alert_policy"

    def test_detect_from_cli_domain(self):
        """Test resource type detection from x-ves-cli-domain as fallback."""
        enricher = NamespaceScopeEnricher()
        spec = {
            "info": {
                "title": "",  # Empty title to fall through
                "x-ves-cli-domain": "virtual",
            },
            "paths": {},
        }
        result = enricher._detect_resource_type(spec)
        assert result == "virtual"

    def test_detect_empty_spec(self):
        """Test resource type detection from empty spec."""
        enricher = NamespaceScopeEnricher()
        spec = {}
        result = enricher._detect_resource_type(spec)
        assert result == ""


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_enrich_empty_spec(self):
        """Test enriching an empty specification."""
        enricher = NamespaceScopeEnricher()
        spec = {}
        result = enricher.enrich_spec(spec)
        assert "info" in result
        assert "x-ves-namespace-scope" in result["info"]
        assert result["info"]["x-ves-namespace-scope"] == "any"

    def test_enrich_spec_with_none_info(self):
        """Test enriching spec where info might be None-like."""
        enricher = NamespaceScopeEnricher()
        spec = {
            "info": {},
            "paths": {},
        }
        result = enricher.enrich_spec(spec)
        assert "x-ves-namespace-scope" in result["info"]

    def test_scope_case_insensitivity(self):
        """Test that resource matching is case-appropriate."""
        enricher = NamespaceScopeEnricher()
        # Resources should be lowercase in config
        assert enricher._determine_scope("alert_policy") == "system"
        # Unknown case variations should fallback to default
        assert enricher._determine_scope("ALERT_POLICY") == "any"

    def test_special_characters_in_title(self):
        """Test handling titles with special characters."""
        enricher = NamespaceScopeEnricher()
        spec = {
            "info": {"title": "Alert-Policy (v2) API"},
            "paths": {},
        }
        result = enricher.enrich_spec(spec)
        assert "x-ves-namespace-scope" in result["info"]


class TestConfiguredResources:
    """Test all configured system-scoped resources."""

    @pytest.mark.parametrize(
        "resource",
        [
            "alert_policy",
            "alert_policy_set",
            "alert_receiver",
            "api_credential",
            "aws_vpc_site",
            "azure_vnet_site",
            "gcp_vpc_site",
            "fleet",
            "namespace",
            "role",
            "user",
            "certificate",
            "global_network",
            "virtual_network",
        ],
    )
    def test_system_scoped_resources(self, resource):
        """Test that known system resources are correctly scoped."""
        enricher = NamespaceScopeEnricher()
        assert enricher._determine_scope(resource) == "system"

    def test_shared_scoped_resource(self):
        """Test that namespace_role_binding is shared scoped."""
        enricher = NamespaceScopeEnricher()
        assert enricher._determine_scope("namespace_role_binding") == "shared"

    @pytest.mark.parametrize(
        "resource",
        [
            "http_loadbalancer",
            "origin_pool",
            "tcp_loadbalancer",
            "healthcheck",
            "app_firewall",
            "waf",
            "service_policy",
            "rate_limiter",
        ],
    )
    def test_any_scoped_resources(self, resource):
        """Test that common user resources are any scoped."""
        enricher = NamespaceScopeEnricher()
        assert enricher._determine_scope(resource) == "any"

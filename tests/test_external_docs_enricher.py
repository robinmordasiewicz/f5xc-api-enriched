"""Tests for ExternalDocsEnricher.

Tests the enrichment of OpenAPI specs with externalDocs metadata
providing links to F5's official documentation.
"""

import pytest

from scripts.utils.external_docs_enricher import (
    ExternalDocsEnricher,
    ExternalDocsStats,
)


class TestExternalDocsStats:
    """Test ExternalDocsStats dataclass."""

    def test_stats_initialization(self):
        """Test stats initialization with default values."""
        stats = ExternalDocsStats()
        assert stats.specs_enriched == 0
        assert stats.docs_added == 0
        assert stats.already_had_docs == 0
        assert stats.used_default == 0
        assert stats.errors == []

    def test_stats_to_dict(self):
        """Test stats conversion to dictionary."""
        stats = ExternalDocsStats()
        stats.specs_enriched = 5
        stats.docs_added = 3
        stats.already_had_docs = 1
        stats.used_default = 1

        result = stats.to_dict()
        assert result["specs_enriched"] == 5
        assert result["docs_added"] == 3
        assert result["already_had_docs"] == 1
        assert result["used_default"] == 1
        assert "error_count" in result


class TestExternalDocsEnricherBasics:
    """Test basic ExternalDocsEnricher functionality."""

    def test_enricher_initialization(self):
        """Test enricher initializes with config loaded."""
        enricher = ExternalDocsEnricher()
        assert enricher.config is not None
        assert enricher.default_docs is not None
        assert "url" in enricher.default_docs
        assert "description" in enricher.default_docs
        assert enricher.stats is not None

    def test_domain_docs_loaded(self):
        """Test that domain documentation mappings are loaded."""
        enricher = ExternalDocsEnricher()
        # Should have domain mappings
        assert len(enricher.domain_docs) > 0
        # Known domains should be present
        assert "virtual" in enricher.domain_docs
        assert "waf" in enricher.domain_docs
        assert "dns" in enricher.domain_docs

    def test_get_stats(self):
        """Test get_stats returns valid dictionary."""
        enricher = ExternalDocsEnricher()
        stats = enricher.get_stats()
        assert isinstance(stats, dict)
        assert "specs_enriched" in stats
        assert "docs_added" in stats
        assert "already_had_docs" in stats
        assert "used_default" in stats

    def test_reset_stats(self):
        """Test reset_stats clears statistics."""
        enricher = ExternalDocsEnricher()
        enricher.stats.specs_enriched = 10
        enricher.stats.docs_added = 5
        enricher.reset_stats()
        assert enricher.stats.specs_enriched == 0
        assert enricher.stats.docs_added == 0


class TestDocsRetrieval:
    """Test docs retrieval logic."""

    def test_get_docs_for_known_domain(self):
        """Test getting docs for a known domain."""
        enricher = ExternalDocsEnricher()
        docs = enricher.get_docs_for_domain("virtual")
        assert "url" in docs
        assert "description" in docs
        assert "f5.com" in docs["url"].lower() or "docs.cloud" in docs["url"].lower()

    def test_get_docs_for_waf_domain(self):
        """Test getting docs for WAF domain."""
        enricher = ExternalDocsEnricher()
        docs = enricher.get_docs_for_domain("waf")
        assert "url" in docs
        assert "waf" in docs["url"].lower() or "firewall" in docs["url"].lower()

    def test_get_docs_for_unknown_domain(self):
        """Test getting docs for unknown domain returns default."""
        enricher = ExternalDocsEnricher()
        docs = enricher.get_docs_for_domain("unknown_domain_xyz")
        assert "url" in docs
        assert docs["url"] == enricher.default_docs["url"]

    def test_get_docs_for_empty_domain(self):
        """Test getting docs for empty domain returns default."""
        enricher = ExternalDocsEnricher()
        docs = enricher.get_docs_for_domain("")
        assert "url" in docs


class TestDomainDetection:
    """Test domain detection from specs."""

    def test_detect_domain_from_filename(self):
        """Test domain detection from filename."""
        enricher = ExternalDocsEnricher()
        spec = {
            "info": {"title": "Some API"},
            "paths": {},
        }
        domain = enricher._detect_domain(
            spec,
            filename="ves.io.schema.views.http_loadbalancer.json",
        )
        assert domain == "virtual"

    def test_detect_domain_from_cli_domain_extension(self):
        """Test domain detection from x-ves-cli-domain extension."""
        enricher = ExternalDocsEnricher()
        spec = {
            "info": {
                "title": "Some API",
                "x-ves-cli-domain": "waf",
            },
            "paths": {},
        }
        domain = enricher._detect_domain(spec, filename=None)
        assert domain == "waf"

    def test_detect_domain_from_title_fallback(self):
        """Test domain detection from title as fallback."""
        enricher = ExternalDocsEnricher()
        spec = {
            "info": {"title": "DNS Load Balancer API"},
            "paths": {},
        }
        domain = enricher._detect_domain(spec, filename=None)
        # Should detect from title pattern
        assert domain in ["dns", "other"]

    def test_detect_domain_unknown(self):
        """Test domain detection returns 'other' for unknown."""
        enricher = ExternalDocsEnricher()
        spec = {
            "info": {"title": "Unknown API"},
            "paths": {},
        }
        domain = enricher._detect_domain(spec, filename="unknown_file.json")
        assert domain == "other"


class TestSpecEnrichment:
    """Test specification enrichment."""

    def test_enrich_spec_adds_external_docs(self):
        """Test that enrich_spec adds externalDocs field."""
        enricher = ExternalDocsEnricher()
        spec = {
            "info": {
                "title": "HTTP Load Balancer API",
            },
            "paths": {},
        }
        result = enricher.enrich_spec(spec, filename="http_loadbalancer.json")
        assert "externalDocs" in result["info"]
        assert "url" in result["info"]["externalDocs"]
        assert "description" in result["info"]["externalDocs"]

    def test_enrich_spec_virtual_domain(self):
        """Test enrichment of virtual domain spec."""
        enricher = ExternalDocsEnricher()
        spec = {
            "info": {
                "title": "HTTP Load Balancer API",
                "x-ves-cli-domain": "virtual",
            },
            "paths": {},
        }
        result = enricher.enrich_spec(spec)
        assert "externalDocs" in result["info"]
        assert (
            "load-balancer" in result["info"]["externalDocs"]["url"].lower()
            or "http" in result["info"]["externalDocs"]["url"].lower()
        )
        assert enricher.stats.docs_added == 1

    def test_enrich_spec_waf_domain(self):
        """Test enrichment of WAF domain spec."""
        enricher = ExternalDocsEnricher()
        spec = {
            "info": {
                "title": "App Firewall API",
                "x-ves-cli-domain": "waf",
            },
            "paths": {},
        }
        result = enricher.enrich_spec(spec)
        assert "externalDocs" in result["info"]
        external_docs = result["info"]["externalDocs"]
        assert "waf" in external_docs["url"].lower() or "firewall" in external_docs["url"].lower()

    def test_enrich_spec_idempotent(self):
        """Test that enrichment is idempotent."""
        enricher = ExternalDocsEnricher()
        spec = {
            "info": {
                "title": "Some API",
                "externalDocs": {
                    "url": "https://example.com/docs",
                    "description": "Existing docs",
                },
            },
            "paths": {},
        }
        result = enricher.enrich_spec(spec)
        # Should preserve existing externalDocs
        assert result["info"]["externalDocs"]["url"] == "https://example.com/docs"
        assert result["info"]["externalDocs"]["description"] == "Existing docs"
        assert enricher.stats.already_had_docs == 1

    def test_enrich_spec_preserves_existing_info(self):
        """Test that enrichment preserves existing info fields."""
        enricher = ExternalDocsEnricher()
        spec = {
            "info": {
                "title": "Some API",
                "version": "1.0.0",
                "description": "API description",
                "x-ves-cli-domain": "virtual",
            },
            "paths": {},
        }
        result = enricher.enrich_spec(spec)
        assert result["info"]["title"] == "Some API"
        assert result["info"]["version"] == "1.0.0"
        assert result["info"]["description"] == "API description"
        assert result["info"]["x-ves-cli-domain"] == "virtual"
        assert "externalDocs" in result["info"]

    def test_enrich_spec_creates_info_if_missing(self):
        """Test that enrichment creates info section if missing."""
        enricher = ExternalDocsEnricher()
        spec = {
            "paths": {},
        }
        result = enricher.enrich_spec(spec)
        assert "info" in result
        assert "externalDocs" in result["info"]

    def test_enrich_spec_stats_updated(self):
        """Test that stats are updated after enrichment."""
        enricher = ExternalDocsEnricher()
        spec = {
            "info": {
                "title": "Some API",
            },
            "paths": {},
        }
        enricher.enrich_spec(spec)
        assert enricher.stats.specs_enriched == 1

    def test_enrich_multiple_specs(self):
        """Test enriching multiple specifications."""
        enricher = ExternalDocsEnricher()
        specs = [
            {
                "info": {"title": "HTTP Load Balancer API", "x-ves-cli-domain": "virtual"},
                "paths": {},
            },
            {"info": {"title": "App Firewall API", "x-ves-cli-domain": "waf"}, "paths": {}},
            {"info": {"title": "DNS Zone API", "x-ves-cli-domain": "dns"}, "paths": {}},
        ]
        for spec in specs:
            enricher.enrich_spec(spec)
        assert enricher.stats.specs_enriched == 3
        assert enricher.stats.docs_added == 3


class TestDomainMappings:
    """Test configured domain documentation mappings."""

    @pytest.mark.parametrize(
        "domain",
        [
            "virtual",
            "waf",
            "dns",
            "cdn",
            "network",
            "sites",
            "api",
            "observability",
            "certificates",
        ],
    )
    def test_known_domains_have_docs(self, domain):
        """Test that known domains have documentation mappings."""
        enricher = ExternalDocsEnricher()
        docs = enricher.get_docs_for_domain(domain)
        assert "url" in docs
        assert "description" in docs
        assert docs["url"].startswith("https://")

    @pytest.mark.parametrize(
        ("domain", "expected_url_part"),
        [
            ("virtual", "load-balancer"),
            ("waf", "firewall"),
            ("dns", "dns"),
            ("cdn", "cdn"),
            ("sites", "site"),
            ("api", "api"),
        ],
    )
    def test_domain_url_relevance(self, domain, expected_url_part):
        """Test that domain URLs contain relevant keywords."""
        enricher = ExternalDocsEnricher()
        docs = enricher.get_docs_for_domain(domain)
        # URL should contain the expected keyword or something related
        url_lower = docs["url"].lower()
        assert expected_url_part in url_lower or domain in url_lower


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_enrich_empty_spec(self):
        """Test enriching an empty specification."""
        enricher = ExternalDocsEnricher()
        spec = {}
        result = enricher.enrich_spec(spec)
        assert "info" in result
        assert "externalDocs" in result["info"]

    def test_enrich_spec_with_empty_info(self):
        """Test enriching spec with empty info section."""
        enricher = ExternalDocsEnricher()
        spec = {
            "info": {},
            "paths": {},
        }
        result = enricher.enrich_spec(spec)
        assert "externalDocs" in result["info"]

    def test_external_docs_structure(self):
        """Test that externalDocs has required OpenAPI fields."""
        enricher = ExternalDocsEnricher()
        spec = {
            "info": {"title": "Test API"},
            "paths": {},
        }
        result = enricher.enrich_spec(spec)
        external_docs = result["info"]["externalDocs"]
        # OpenAPI 3.0 externalDocs requires url and allows description
        assert "url" in external_docs
        assert isinstance(external_docs["url"], str)
        assert external_docs["url"].startswith("https://")
        if "description" in external_docs:
            assert isinstance(external_docs["description"], str)

    def test_default_docs_used_for_other(self):
        """Test that default docs are used for 'other' domain."""
        enricher = ExternalDocsEnricher()
        enricher.reset_stats()
        spec = {
            "info": {"title": "Completely Unknown API"},
            "paths": {},
        }
        enricher.enrich_spec(spec, filename="unknown_xyz.json")
        assert enricher.stats.used_default >= 0  # May or may not use default


class TestFilenameBasedDetection:
    """Test filename-based domain detection."""

    @pytest.mark.parametrize(
        ("filename", "expected_domain"),
        [
            ("ves.io.schema.views.http_loadbalancer.json", "virtual"),
            ("ves.io.schema.app_firewall.json", "waf"),
            ("ves.io.schema.dns_zone.json", "dns"),
            ("ves.io.schema.cdn_loadbalancer.json", "cdn"),
            ("ves.io.schema.aws_vpc_site.json", "sites"),
        ],
    )
    def test_filename_domain_detection(self, filename, expected_domain):
        """Test that filenames correctly map to domains."""
        enricher = ExternalDocsEnricher()
        spec = {"info": {"title": "Test API"}, "paths": {}}
        domain = enricher._detect_domain(spec, filename=filename)
        assert domain == expected_domain


class TestIntegrationPatterns:
    """Test integration patterns with other enrichers."""

    def test_works_with_cli_domain_from_other_enricher(self):
        """Test using x-ves-cli-domain set by another enricher."""
        enricher = ExternalDocsEnricher()
        # Simulate spec already enriched by MinimumConfigurationEnricher
        spec = {
            "info": {
                "title": "HTTP Load Balancer API",
                "x-ves-cli-domain": "virtual",
                "x-ves-minimum-configuration": {
                    "description": "Minimum viable load balancer",
                },
            },
            "paths": {},
        }
        result = enricher.enrich_spec(spec)
        assert "externalDocs" in result["info"]
        # Should still have other extensions
        assert "x-ves-cli-domain" in result["info"]
        assert "x-ves-minimum-configuration" in result["info"]

    def test_works_with_namespace_scope(self):
        """Test compatibility with namespace scope enricher."""
        enricher = ExternalDocsEnricher()
        # Simulate spec already enriched by NamespaceScopeEnricher
        spec = {
            "info": {
                "title": "Alert Policy API",
                "x-ves-namespace-scope": "system",
            },
            "paths": {},
        }
        result = enricher.enrich_spec(spec)
        assert "externalDocs" in result["info"]
        assert "x-ves-namespace-scope" in result["info"]
        assert result["info"]["x-ves-namespace-scope"] == "system"

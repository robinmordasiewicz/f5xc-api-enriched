"""Unit tests for DescriptionEnricher."""

import pytest

from scripts.utils.description_enricher import (
    DescriptionEnricher,
    DescriptionEnrichmentStats,
    get_description_enricher,
    get_domain_descriptions,
)


@pytest.fixture
def enricher():
    """Create enricher with default config."""
    return DescriptionEnricher()


@pytest.fixture
def spec_with_info():
    """Create a spec with info section."""
    return {
        "info": {
            "title": "F5 XC Virtual API",
            "description": "Original description",
            "x-ves-cli-domain": "virtual",
        },
        "paths": {},
    }


@pytest.fixture
def spec_without_domain():
    """Create a spec without domain classification."""
    return {
        "info": {
            "title": "Unknown API",
            "description": "Some API",
        },
        "paths": {},
    }


@pytest.fixture
def spec_without_info():
    """Create a spec without info section."""
    return {
        "paths": {},
    }


class TestDescriptionEnricherBasics:
    """Test basic enricher functionality."""

    def test_initialization(self):
        """Test enricher initializes correctly."""
        enricher = DescriptionEnricher()
        assert enricher is not None
        assert enricher.config_path is not None

    def test_config_version(self, enricher):
        """Test config version is loaded."""
        version = enricher.get_config_version()
        assert version is not None
        assert isinstance(version, str)

    def test_configured_domains(self, enricher):
        """Test configured domains list."""
        domains = enricher.get_configured_domains()
        assert isinstance(domains, list)
        # Virtual domain should be configured (from prototype)
        assert "virtual" in domains

    def test_stats_initialization(self, enricher):
        """Test stats are initialized to zero."""
        stats = enricher.get_stats()
        assert stats["specs_processed"] == 0
        assert stats["descriptions_applied"] == 0
        assert stats["descriptions_skipped"] == 0
        assert stats["domains_without_config"] == []


class TestDescriptionRetrieval:
    """Test description retrieval methods."""

    def test_get_short_description(self, enricher):
        """Test getting short description for virtual domain."""
        desc = enricher.get_description("virtual", tier="short")
        assert desc is not None
        assert len(desc) <= 60
        assert "load balancing" in desc.lower() or "http" in desc.lower()

    def test_get_medium_description(self, enricher):
        """Test getting medium description for virtual domain."""
        desc = enricher.get_description("virtual", tier="medium")
        assert desc is not None
        assert len(desc) <= 150

    def test_get_long_description(self, enricher):
        """Test getting long description for virtual domain."""
        desc = enricher.get_description("virtual", tier="long")
        assert desc is not None
        assert len(desc) <= 500

    def test_get_description_unknown_domain(self, enricher):
        """Test getting description for unknown domain."""
        desc = enricher.get_description("unknown_domain", tier="short")
        assert desc is None

    def test_get_all_descriptions(self, enricher):
        """Test getting all description tiers."""
        descs = enricher.get_all_descriptions("virtual")
        assert descs is not None
        assert "short" in descs
        assert "medium" in descs
        assert "long" in descs

    def test_has_description(self, enricher):
        """Test has_description method."""
        assert enricher.has_description("virtual") is True
        assert enricher.has_description("unknown_domain") is False


class TestSpecEnrichment:
    """Test spec enrichment functionality."""

    def test_enrich_spec_with_domain(self, enricher, spec_with_info):
        """Test enriching spec with known domain."""
        result = enricher.enrich_spec(spec_with_info, domain="virtual")
        assert "info" in result
        assert "description" in result["info"]
        # Should use enriched long description
        desc = result["info"]["description"]
        assert len(desc) > 0
        # Should be enriched (not original)
        assert desc != "Original description"

    def test_enrich_spec_extracts_domain(self, enricher, spec_with_info):
        """Test enriching spec that has x-ves-cli-domain."""
        result = enricher.enrich_spec(spec_with_info)
        # Should extract domain from x-ves-cli-domain
        assert result["info"]["description"] != "Original description"

    def test_enrich_spec_without_domain(self, enricher, spec_without_domain):
        """Test enriching spec without domain classification."""
        result = enricher.enrich_spec(spec_without_domain)
        # Should skip enrichment, keep original description
        assert result["info"]["description"] == "Some API"

    def test_enrich_spec_unknown_domain(self, enricher, spec_with_info):
        """Test enriching spec with unknown domain."""
        result = enricher.enrich_spec(spec_with_info, domain="unknown_domain")
        # Should skip enrichment, keep original description
        assert result["info"]["description"] == "Original description"

    def test_enrich_spec_without_info(self, enricher, spec_without_info):
        """Test enriching spec without info section."""
        result = enricher.enrich_spec(spec_without_info, domain="virtual")
        # Should add info section with description
        assert "info" in result
        assert "description" in result["info"]


class TestStatistics:
    """Test statistics tracking."""

    def test_stats_after_successful_enrichment(self, enricher, spec_with_info):
        """Test stats after successful enrichment."""
        enricher.enrich_spec(spec_with_info, domain="virtual")
        stats = enricher.get_stats()
        assert stats["specs_processed"] == 1
        assert stats["descriptions_applied"] == 1
        assert stats["descriptions_skipped"] == 0

    def test_stats_after_skipped_enrichment(self, enricher, spec_without_domain):
        """Test stats after skipped enrichment."""
        enricher.enrich_spec(spec_without_domain)
        stats = enricher.get_stats()
        assert stats["specs_processed"] == 1
        assert stats["descriptions_applied"] == 0
        assert stats["descriptions_skipped"] == 1

    def test_stats_tracks_missing_domains(self, enricher, spec_with_info):
        """Test stats tracks domains without config."""
        enricher.enrich_spec(spec_with_info, domain="unknown_domain1")
        enricher.enrich_spec(spec_with_info, domain="unknown_domain2")
        stats = enricher.get_stats()
        assert "unknown_domain1" in stats["domains_without_config"]
        assert "unknown_domain2" in stats["domains_without_config"]


class TestModuleLevelFunctions:
    """Test module-level convenience functions."""

    def test_get_description_enricher_singleton(self):
        """Test singleton pattern for module-level enricher."""
        e1 = get_description_enricher()
        e2 = get_description_enricher()
        assert e1 is e2

    def test_get_domain_descriptions_convenience(self):
        """Test convenience function for getting descriptions."""
        descs = get_domain_descriptions("virtual")
        assert descs is not None
        assert "short" in descs
        assert "medium" in descs
        assert "long" in descs

    def test_get_domain_descriptions_unknown(self):
        """Test convenience function for unknown domain."""
        descs = get_domain_descriptions("unknown_domain")
        assert descs is None


class TestDescriptionStats:
    """Test DescriptionEnrichmentStats dataclass."""

    def test_stats_dataclass_defaults(self):
        """Test stats dataclass has correct defaults."""
        stats = DescriptionEnrichmentStats()
        assert stats.specs_processed == 0
        assert stats.descriptions_applied == 0
        assert stats.descriptions_skipped == 0
        assert stats.domains_without_config == []

    def test_stats_to_dict(self):
        """Test stats conversion to dictionary."""
        stats = DescriptionEnrichmentStats(
            specs_processed=10,
            descriptions_applied=5,
            descriptions_skipped=3,
            domains_without_config=["a", "b"],
        )
        result = stats.to_dict()
        assert result["specs_processed"] == 10
        assert result["descriptions_applied"] == 5
        assert result["descriptions_skipped"] == 3
        assert result["domains_without_config"] == ["a", "b"]


class TestDescriptionValidation:
    """Test description length validation."""

    def test_short_description_length(self, enricher):
        """Verify short descriptions are within 60 chars."""
        for domain in enricher.get_configured_domains():
            desc = enricher.get_description(domain, tier="short")
            if desc:
                assert len(desc) <= 60, f"Short description for {domain} exceeds 60 chars"

    def test_medium_description_length(self, enricher):
        """Verify medium descriptions are within 150 chars."""
        for domain in enricher.get_configured_domains():
            desc = enricher.get_description(domain, tier="medium")
            if desc:
                assert len(desc) <= 150, f"Medium description for {domain} exceeds 150 chars"

    def test_long_description_length(self, enricher):
        """Verify long descriptions are within 500 chars."""
        for domain in enricher.get_configured_domains():
            desc = enricher.get_description(domain, tier="long")
            if desc:
                assert len(desc) <= 500, f"Long description for {domain} exceeds 500 chars"

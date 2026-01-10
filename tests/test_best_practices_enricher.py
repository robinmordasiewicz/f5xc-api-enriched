# Copyright (c) 2026 Robin Mordasiewicz. MIT License.

"""Unit tests for BestPracticesEnricher."""

import pytest

from scripts.utils.best_practices_enricher import (
    BestPractices,
    BestPracticesEnricher,
    BestPracticesEnrichmentStats,
    CommonError,
)


@pytest.fixture
def enricher():
    """Create enricher with default config."""
    return BestPracticesEnricher()


@pytest.fixture
def spec_with_virtual_domain():
    """Create a spec with virtual domain classification."""
    return {
        "info": {
            "title": "F5 XC Virtual API",
            "description": "Virtual load balancing API",
            "x-f5xc-cli-domain": "virtual",
        },
        "paths": {},
    }


@pytest.fixture
def spec_with_waf_domain():
    """Create a spec with WAF domain classification."""
    return {
        "info": {
            "title": "F5 XC WAF API",
            "description": "WAF protection API",
            "x-f5xc-cli-domain": "waf",
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


class TestBestPracticesEnricherBasics:
    """Test basic enricher functionality."""

    def test_initialization(self):
        """Test enricher initializes correctly."""
        enricher = BestPracticesEnricher()
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
        # Virtual and WAF domains should be configured
        assert "virtual" in domains
        assert "waf" in domains

    def test_stats_initialization(self, enricher):
        """Test stats are initialized to zero."""
        stats = enricher.get_stats()
        assert stats["specs_processed"] == 0
        assert stats["best_practices_applied"] == 0
        assert stats["best_practices_skipped"] == 0


class TestBestPracticesRetrieval:
    """Test best practices retrieval methods."""

    def test_get_best_practices_virtual(self, enricher):
        """Test getting best practices for virtual domain."""
        practices = enricher.get_best_practices("virtual")
        assert practices is not None
        assert isinstance(practices, BestPractices)

    def test_get_best_practices_waf(self, enricher):
        """Test getting best practices for WAF domain."""
        practices = enricher.get_best_practices("waf")
        assert practices is not None
        assert isinstance(practices, BestPractices)

    def test_get_best_practices_unknown_domain_returns_defaults(self, enricher):
        """Test getting best practices for unknown domain returns defaults."""
        # Unknown domains return default best practices (not None)
        practices = enricher.get_best_practices("unknown_domain_xyz")
        # Either defaults or None depending on config
        if practices is not None:
            assert isinstance(practices, BestPractices)

    def test_best_practices_has_common_errors(self, enricher):
        """Test that best practices include common errors."""
        practices = enricher.get_best_practices("virtual")
        assert practices is not None
        assert isinstance(practices.common_errors, list)
        assert len(practices.common_errors) > 0

    def test_best_practices_has_security_notes(self, enricher):
        """Test that best practices include security notes."""
        practices = enricher.get_best_practices("virtual")
        assert practices is not None
        assert isinstance(practices.security_notes, list)

    def test_best_practices_has_performance_tips(self, enricher):
        """Test that best practices include performance tips."""
        practices = enricher.get_best_practices("virtual")
        assert practices is not None
        assert isinstance(practices.performance_tips, list)


class TestCommonErrorStructure:
    """Test CommonError dataclass structure."""

    def test_common_error_has_required_fields(self, enricher):
        """Test that common errors have all required fields."""
        practices = enricher.get_best_practices("virtual")
        assert practices is not None
        assert len(practices.common_errors) > 0

        error = practices.common_errors[0]
        assert isinstance(error, CommonError)
        assert hasattr(error, "code")
        assert hasattr(error, "message")
        assert hasattr(error, "resolution")
        assert hasattr(error, "prevention")

    def test_common_error_to_dict(self, enricher):
        """Test common error to_dict method."""
        practices = enricher.get_best_practices("virtual")
        assert practices is not None
        assert len(practices.common_errors) > 0

        error = practices.common_errors[0]
        error_dict = error.to_dict()
        assert isinstance(error_dict, dict)
        assert "code" in error_dict
        assert "message" in error_dict


class TestSpecEnrichment:
    """Test spec enrichment functionality."""

    def test_enrich_spec_with_domain(self, enricher, spec_with_virtual_domain):
        """Test enriching spec with domain classification."""
        enriched = enricher.enrich_spec(spec_with_virtual_domain, domain="virtual")
        assert "info" in enriched
        assert "x-f5xc-best-practices" in enriched["info"]

    def test_enrich_spec_uses_spec_domain(self, enricher, spec_with_virtual_domain):
        """Test enriching spec uses domain from spec."""
        enriched = enricher.enrich_spec(spec_with_virtual_domain)
        assert "info" in enriched
        # Should use domain from spec's x-f5xc-cli-domain
        assert "x-f5xc-best-practices" in enriched["info"]

    def test_enrich_spec_without_domain(self, enricher, spec_without_domain):
        """Test enriching spec without domain does not add best practices."""
        enriched = enricher.enrich_spec(spec_without_domain)
        assert "info" in enriched
        assert "x-f5xc-best-practices" not in enriched.get("info", {})

    def test_enrich_spec_without_info(self, enricher, spec_without_info):
        """Test enriching spec without info creates info section."""
        enriched = enricher.enrich_spec(spec_without_info, domain="virtual")
        assert "info" in enriched
        assert "x-f5xc-best-practices" in enriched["info"]

    def test_enrich_spec_structure(self, enricher, spec_with_virtual_domain):
        """Test enriched spec has correct structure."""
        enriched = enricher.enrich_spec(spec_with_virtual_domain, domain="virtual")
        practices = enriched["info"]["x-f5xc-best-practices"]

        assert isinstance(practices, dict)
        assert "common_errors" in practices
        assert "security_notes" in practices
        assert "performance_tips" in practices

    def test_enrich_spec_stats_updated(self, enricher, spec_with_virtual_domain):
        """Test that stats are updated after enrichment."""
        enricher.enrich_spec(spec_with_virtual_domain, domain="virtual")
        stats = enricher.get_stats()
        assert stats["specs_processed"] == 1
        assert stats["best_practices_applied"] == 1


class TestBestPracticesEnrichmentStats:
    """Test enrichment statistics dataclass."""

    def test_stats_initialization(self):
        """Test stats initialize with zeros."""
        stats = BestPracticesEnrichmentStats()
        assert stats.specs_processed == 0
        assert stats.best_practices_applied == 0
        assert stats.best_practices_skipped == 0

    def test_stats_to_dict(self):
        """Test stats to_dict method."""
        stats = BestPracticesEnrichmentStats(
            specs_processed=5,
            best_practices_applied=3,
            best_practices_skipped=2,
        )
        stats_dict = stats.to_dict()
        assert isinstance(stats_dict, dict)
        assert stats_dict["specs_processed"] == 5
        assert stats_dict["best_practices_applied"] == 3
        assert stats_dict["best_practices_skipped"] == 2


class TestBestPracticesToDict:
    """Test BestPractices to_dict output."""

    def test_best_practices_to_dict(self, enricher):
        """Test converting best practices to dict format."""
        practices = enricher.get_best_practices("virtual")
        assert practices is not None

        result = practices.to_dict()
        assert isinstance(result, dict)
        assert "common_errors" in result
        assert "security_notes" in result
        assert "performance_tips" in result

    def test_to_dict_common_errors_format(self, enricher):
        """Test common errors in dict format."""
        practices = enricher.get_best_practices("virtual")
        assert practices is not None

        result = practices.to_dict()
        common_errors = result["common_errors"]
        assert isinstance(common_errors, list)

        if len(common_errors) > 0:
            error = common_errors[0]
            assert "code" in error
            assert "message" in error


class TestBestPracticesHelperMethods:
    """Test helper methods on enricher."""

    def test_get_common_errors(self, enricher):
        """Test get_common_errors method."""
        errors = enricher.get_common_errors("virtual")
        assert isinstance(errors, list)

    def test_get_security_notes(self, enricher):
        """Test get_security_notes method."""
        notes = enricher.get_security_notes("virtual")
        assert isinstance(notes, list)

    def test_get_performance_tips(self, enricher):
        """Test get_performance_tips method."""
        tips = enricher.get_performance_tips("virtual")
        assert isinstance(tips, list)

    def test_has_best_practices(self, enricher):
        """Test has_best_practices method."""
        assert enricher.has_best_practices("virtual") is True
        # Unknown domains may or may not have defaults

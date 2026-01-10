# Copyright (c) 2026 Robin Mordasiewicz. MIT License.

"""Unit tests for ErrorResolutionEnricher."""

import pytest

from scripts.utils.error_resolution_enricher import (
    DiagnosticStep,
    ErrorResolutionEnricher,
    ErrorResolutionEnrichmentStats,
    HttpError,
    ResourceErrorPattern,
)


@pytest.fixture
def enricher():
    """Create enricher with default config."""
    return ErrorResolutionEnricher()


@pytest.fixture
def sample_index():
    """Create a sample index for enrichment."""
    return {
        "version": "1.0.0",
        "specifications": [],
    }


class TestErrorResolutionEnricherBasics:
    """Test basic enricher functionality."""

    def test_initialization(self):
        """Test enricher initializes correctly."""
        enricher = ErrorResolutionEnricher()
        assert enricher is not None
        assert enricher.config_path is not None

    def test_config_version(self, enricher):
        """Test config version is loaded."""
        version = enricher.get_config_version()
        assert version is not None
        assert isinstance(version, str)

    def test_stats_initialization(self, enricher):
        """Test stats are initialized correctly."""
        stats = enricher.get_stats()
        assert stats["indexes_processed"] == 0
        assert stats["http_errors_loaded"] > 0  # Should load from config


class TestHttpErrorRetrieval:
    """Test HTTP error retrieval methods."""

    def test_get_http_error_401(self, enricher):
        """Test getting 401 error details."""
        error = enricher.get_http_error(401)
        assert error is not None
        assert isinstance(error, HttpError)
        assert error.code == 401

    def test_get_http_error_403(self, enricher):
        """Test getting 403 error details."""
        error = enricher.get_http_error(403)
        assert error is not None
        assert error.code == 403

    def test_get_http_error_404(self, enricher):
        """Test getting 404 error details."""
        error = enricher.get_http_error(404)
        assert error is not None
        assert error.code == 404

    def test_get_http_error_500(self, enricher):
        """Test getting 500 error details."""
        error = enricher.get_http_error(500)
        assert error is not None
        assert error.code == 500

    def test_get_http_error_unknown(self, enricher):
        """Test getting unknown error code returns None."""
        error = enricher.get_http_error(999)
        assert error is None

    def test_get_all_error_codes(self, enricher):
        """Test getting all configured error codes."""
        codes = enricher.get_all_error_codes()
        assert isinstance(codes, list)
        assert len(codes) > 0
        assert 401 in codes
        assert 404 in codes


class TestHttpErrorStructure:
    """Test HttpError dataclass structure."""

    def test_http_error_has_required_fields(self, enricher):
        """Test HTTP errors have required fields."""
        error = enricher.get_http_error(401)
        assert error is not None

        assert hasattr(error, "code")
        assert hasattr(error, "name")
        assert hasattr(error, "description")
        assert hasattr(error, "common_causes")
        assert hasattr(error, "diagnostic_steps")
        assert hasattr(error, "prevention")
        assert hasattr(error, "related_errors")

    def test_http_error_to_dict(self, enricher):
        """Test HTTP error to_dict method."""
        error = enricher.get_http_error(401)
        assert error is not None

        error_dict = error.to_dict()
        assert isinstance(error_dict, dict)
        assert "code" in error_dict
        assert "name" in error_dict
        assert "description" in error_dict
        assert "common_causes" in error_dict

    def test_http_error_has_common_causes(self, enricher):
        """Test HTTP errors have common causes."""
        error = enricher.get_http_error(401)
        assert error is not None
        assert isinstance(error.common_causes, list)
        assert len(error.common_causes) > 0


class TestDiagnosticSteps:
    """Test diagnostic steps functionality."""

    def test_get_diagnostic_steps(self, enricher):
        """Test getting diagnostic steps for error code."""
        steps = enricher.get_diagnostic_steps(401)
        assert isinstance(steps, list)
        assert len(steps) > 0

    def test_diagnostic_step_structure(self, enricher):
        """Test diagnostic step has correct structure."""
        steps = enricher.get_diagnostic_steps(401)
        assert len(steps) > 0

        step = steps[0]
        assert isinstance(step, DiagnosticStep)
        assert hasattr(step, "step")
        assert hasattr(step, "action")
        assert hasattr(step, "description")

    def test_diagnostic_step_to_dict(self, enricher):
        """Test diagnostic step to_dict method."""
        steps = enricher.get_diagnostic_steps(401)
        step = steps[0]

        step_dict = step.to_dict()
        assert isinstance(step_dict, dict)
        assert "step" in step_dict
        assert "action" in step_dict

    def test_diagnostic_steps_are_ordered(self, enricher):
        """Test diagnostic steps are ordered by step number."""
        steps = enricher.get_diagnostic_steps(401)
        if len(steps) > 1:
            for i in range(len(steps) - 1):
                assert steps[i].step <= steps[i + 1].step


class TestPreventionTips:
    """Test prevention tips functionality."""

    def test_get_prevention_tips(self, enricher):
        """Test getting prevention tips for error code."""
        tips = enricher.get_prevention_tips(401)
        assert isinstance(tips, list)
        assert len(tips) > 0

    def test_prevention_tips_are_strings(self, enricher):
        """Test prevention tips are strings."""
        tips = enricher.get_prevention_tips(401)
        for tip in tips:
            assert isinstance(tip, str)


class TestResourceErrors:
    """Test resource-specific error patterns."""

    def test_get_configured_resources(self, enricher):
        """Test getting configured resources."""
        resources = enricher.get_configured_resources()
        assert isinstance(resources, list)

    def test_get_resource_errors(self, enricher):
        """Test getting resource-specific errors."""
        resources = enricher.get_configured_resources()
        if len(resources) > 0:
            resource = resources[0]
            patterns = enricher.get_resource_errors(resource)
            assert isinstance(patterns, list)

    def test_resource_error_pattern_structure(self, enricher):
        """Test resource error pattern has correct structure."""
        resources = enricher.get_configured_resources()
        if len(resources) > 0:
            patterns = enricher.get_resource_errors(resources[0])
            if len(patterns) > 0:
                pattern = patterns[0]
                assert isinstance(pattern, ResourceErrorPattern)
                assert hasattr(pattern, "error_code")
                assert hasattr(pattern, "pattern")
                assert hasattr(pattern, "resolution")


class TestIndexEnrichment:
    """Test index.json enrichment functionality."""

    def test_enrich_index(self, enricher, sample_index):
        """Test enriching index.json with error resolution."""
        enriched = enricher.enrich_index(sample_index)
        assert "x-f5xc-error-resolution" in enriched

    def test_enriched_index_structure(self, enricher, sample_index):
        """Test enriched index has correct structure."""
        enriched = enricher.enrich_index(sample_index)
        error_data = enriched["x-f5xc-error-resolution"]

        assert isinstance(error_data, dict)
        assert "version" in error_data
        assert "http_errors" in error_data
        assert "resource_errors" in error_data

    def test_enriched_index_http_errors(self, enricher, sample_index):
        """Test enriched index contains HTTP errors."""
        enriched = enricher.enrich_index(sample_index)
        http_errors = enriched["x-f5xc-error-resolution"]["http_errors"]

        assert isinstance(http_errors, dict)
        assert len(http_errors) > 0

    def test_enrich_index_stats_updated(self, enricher, sample_index):
        """Test stats are updated after enrichment."""
        enricher.enrich_index(sample_index)
        stats = enricher.get_stats()
        assert stats["indexes_processed"] == 1
        assert stats["enrichment_applied"] is True


class TestErrorResolutionEnrichmentStats:
    """Test enrichment statistics dataclass."""

    def test_stats_initialization(self):
        """Test stats initialize correctly."""
        stats = ErrorResolutionEnrichmentStats()
        assert stats.indexes_processed == 0
        assert stats.http_errors_loaded == 0
        assert stats.resource_errors_loaded == 0
        assert stats.enrichment_applied is False

    def test_stats_to_dict(self):
        """Test stats to_dict method."""
        stats = ErrorResolutionEnrichmentStats(
            indexes_processed=2,
            http_errors_loaded=10,
            resource_errors_loaded=5,
            enrichment_applied=True,
        )
        stats_dict = stats.to_dict()
        assert isinstance(stats_dict, dict)
        assert stats_dict["indexes_processed"] == 2
        assert stats_dict["http_errors_loaded"] == 10

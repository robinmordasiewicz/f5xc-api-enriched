# Copyright (c) 2026 Robin Mordasiewicz. MIT License.

"""Unit tests for ErrorCatalogBuilder module.

Tests error catalog building functionality including configuration,
error recording, classification, and pattern extraction.
"""

import pytest

from scripts.discovery.error_catalog_builder import (
    BuilderStats,
    EndpointErrors,
    ErrorCatalog,
    ErrorCatalogBuilder,
    ErrorCatalogConfig,
    ErrorEntry,
)


class TestErrorCatalogConfig:
    """Test ErrorCatalogConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = ErrorCatalogConfig()
        assert config.enabled is True
        assert config.max_errors_per_endpoint == 10
        assert config.max_message_length == 200
        assert config.track_frequency is True
        assert config.categorize_errors is True


class TestErrorEntry:
    """Test ErrorEntry dataclass."""

    def test_to_dict(self):
        """Test to_dict method."""
        entry = ErrorEntry(
            status_code=401,
            error_type="authentication",
            message="Invalid token",
            message_pattern="Invalid token",
            endpoint="/api/test",
            method="GET",
            frequency=5,
            resolution="Check API token validity",
        )
        result = entry.to_dict()

        assert result["status_code"] == 401
        assert result["error_type"] == "authentication"
        assert result["message_pattern"] == "Invalid token"
        assert result["frequency"] == 5
        assert result["resolution"] == "Check API token validity"

    def test_to_dict_without_resolution(self):
        """Test to_dict omits empty resolution."""
        entry = ErrorEntry(
            status_code=400,
            error_type="validation",
            message="Invalid request",
            message_pattern="Invalid request",
            endpoint="/api/test",
            method="POST",
        )
        result = entry.to_dict()

        assert "resolution" not in result

    def test_to_extension(self):
        """Test to_extension method."""
        entry = ErrorEntry(
            status_code=404,
            error_type="not_found",
            message="Resource not found",
            message_pattern="Resource not found",
            endpoint="/api/test",
            method="GET",
            frequency=3,
            resolution="Check resource exists",
        )
        result = entry.to_extension()

        assert result["status_code"] == 404
        assert result["error_type"] == "not_found"
        assert result["resolution"] == "Check resource exists"


class TestEndpointErrors:
    """Test EndpointErrors dataclass."""

    def test_to_dict(self):
        """Test to_dict method."""
        entry = ErrorEntry(
            status_code=401,
            error_type="authentication",
            message="Auth error",
            message_pattern="Auth error",
            endpoint="/api/test",
            method="GET",
        )
        endpoint_errors = EndpointErrors(
            endpoint="/api/test",
            method="GET",
            errors=[entry],
            total_errors=5,
        )
        result = endpoint_errors.to_dict()

        assert result["endpoint"] == "/api/test"
        assert result["method"] == "GET"
        assert result["total_errors"] == 5
        assert len(result["errors"]) == 1


class TestErrorCatalog:
    """Test ErrorCatalog dataclass."""

    def test_to_dict(self):
        """Test to_dict method."""
        catalog = ErrorCatalog(
            total_errors=10,
            unique_patterns=5,
            discovered_at="2024-01-01T00:00:00Z",
        )
        result = catalog.to_dict()

        assert result["total_errors"] == 10
        assert result["unique_patterns"] == 5
        assert result["discovered_at"] == "2024-01-01T00:00:00Z"

    def test_to_extension(self):
        """Test to_extension method."""
        entry = ErrorEntry(
            status_code=401,
            error_type="authentication",
            message="Auth error",
            message_pattern="Auth error",
            endpoint="/api/test",
            method="GET",
            resolution="Check token",
        )
        catalog = ErrorCatalog()
        catalog.errors_by_status[401] = [entry]
        result = catalog.to_extension()

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["status_code"] == 401


class TestBuilderStats:
    """Test BuilderStats dataclass."""

    def test_default_values(self):
        """Test default stats values."""
        stats = BuilderStats()
        assert stats.errors_recorded == 0
        assert stats.errors_deduplicated == 0
        assert stats.patterns_extracted == 0
        assert stats.resolutions_generated == 0

    def test_to_dict(self):
        """Test to_dict method."""
        stats = BuilderStats(
            errors_recorded=50,
            errors_deduplicated=10,
            patterns_extracted=40,
            resolutions_generated=35,
        )
        result = stats.to_dict()

        assert result["errors_recorded"] == 50
        assert result["errors_deduplicated"] == 10


class TestErrorCatalogBuilder:
    """Test ErrorCatalogBuilder class."""

    def test_default_initialization(self):
        """Test initialization with default config."""
        builder = ErrorCatalogBuilder()
        assert builder.config.enabled is True
        assert builder.config.max_errors_per_endpoint == 10

    def test_dict_config(self):
        """Test initialization with dict config."""
        config = {
            "enabled": True,
            "max_errors_per_endpoint": 5,
            "max_message_length": 100,
        }
        builder = ErrorCatalogBuilder(config=config)
        assert builder.config.max_errors_per_endpoint == 5
        assert builder.config.max_message_length == 100

    def test_config_object(self):
        """Test initialization with ErrorCatalogConfig object."""
        config = ErrorCatalogConfig(enabled=False)
        builder = ErrorCatalogBuilder(config=config)
        assert builder.config.enabled is False


class TestErrorRecording:
    """Test error recording functionality."""

    def test_record_error_basic(self):
        """Test basic error recording."""
        builder = ErrorCatalogBuilder()
        entry = builder.record_error(
            endpoint="/api/test",
            method="GET",
            status_code=401,
            response_body={"message": "Unauthorized access"},
        )

        assert entry is not None
        assert entry.status_code == 401
        assert entry.endpoint == "/api/test"
        assert entry.method == "GET"

    def test_record_error_disabled(self):
        """Test error recording when disabled."""
        builder = ErrorCatalogBuilder(config={"enabled": False})
        entry = builder.record_error(
            endpoint="/api/test",
            method="GET",
            status_code=401,
            response_body={"message": "Unauthorized"},
        )

        assert entry is None

    def test_record_error_max_limit(self):
        """Test that max errors per endpoint is respected."""
        builder = ErrorCatalogBuilder(config={"max_errors_per_endpoint": 2})

        # Record different error patterns
        for i in range(5):
            builder.record_error(
                endpoint="/api/test",
                method="GET",
                status_code=400 + i,
                response_body={"message": f"Error {i}"},
            )

        errors = builder.get_errors_for_endpoint("/api/test", "GET")
        assert len(errors) == 2

    def test_record_error_deduplication(self):
        """Test that duplicate errors are deduplicated."""
        builder = ErrorCatalogBuilder()

        # Record same error twice
        builder.record_error(
            endpoint="/api/test",
            method="GET",
            status_code=401,
            response_body={"message": "Unauthorized"},
        )
        builder.record_error(
            endpoint="/api/test",
            method="GET",
            status_code=401,
            response_body={"message": "Unauthorized"},
        )

        errors = builder.get_errors_for_endpoint("/api/test", "GET")
        assert len(errors) == 1
        assert errors[0].frequency == 2

    def test_record_error_string_body(self):
        """Test recording error with string body."""
        builder = ErrorCatalogBuilder()
        entry = builder.record_error(
            endpoint="/api/test",
            method="POST",
            status_code=500,
            response_body="Internal server error",
        )

        assert entry is not None
        assert "Internal server error" in entry.message

    def test_record_error_none_body(self):
        """Test recording error with None body."""
        builder = ErrorCatalogBuilder()
        entry = builder.record_error(
            endpoint="/api/test",
            method="GET",
            status_code=503,
            response_body=None,
        )

        assert entry is not None
        assert entry.message == ""


class TestErrorClassification:
    """Test error type classification."""

    @pytest.fixture
    def builder(self):
        """Create a fresh builder for each test."""
        return ErrorCatalogBuilder()

    def test_classify_authentication(self, builder):
        """Test authentication error classification."""
        # Use "Unauthorized" message that matches authentication patterns
        # Note: "Invalid token" would match "invalid" (validation) before "token" (auth)
        entry = builder.record_error(
            endpoint="/api/test",
            method="GET",
            status_code=401,
            response_body={"message": "Unauthorized access - token expired"},
        )

        assert entry.error_type == "authentication"

    def test_classify_authorization(self, builder):
        """Test authorization error classification."""
        entry = builder.record_error(
            endpoint="/api/test",
            method="GET",
            status_code=403,
            response_body={"message": "Access denied"},
        )

        assert entry.error_type == "authorization"

    def test_classify_not_found(self, builder):
        """Test not found error classification."""
        entry = builder.record_error(
            endpoint="/api/test",
            method="GET",
            status_code=404,
            response_body={"message": "Resource not found"},
        )

        assert entry.error_type == "not_found"

    def test_classify_validation(self, builder):
        """Test validation error classification."""
        entry = builder.record_error(
            endpoint="/api/test",
            method="POST",
            status_code=400,
            response_body={"message": "Invalid request format"},
        )

        assert entry.error_type == "validation"

    def test_classify_conflict(self, builder):
        """Test conflict error classification."""
        entry = builder.record_error(
            endpoint="/api/test",
            method="POST",
            status_code=409,
            response_body={"message": "Resource already exists"},
        )

        assert entry.error_type == "conflict"

    def test_classify_rate_limit(self, builder):
        """Test rate limit error classification."""
        entry = builder.record_error(
            endpoint="/api/test",
            method="GET",
            status_code=429,
            response_body={"message": "Too many requests"},
        )

        assert entry.error_type == "rate_limit"

    def test_classify_server_error(self, builder):
        """Test server error classification."""
        entry = builder.record_error(
            endpoint="/api/test",
            method="GET",
            status_code=500,
            response_body={"message": "Internal error occurred"},
        )

        assert entry.error_type == "server_error"


class TestPatternExtraction:
    """Test pattern extraction from error messages."""

    @pytest.fixture
    def builder(self):
        """Create a fresh builder for each test."""
        return ErrorCatalogBuilder()

    def test_extract_uuid_pattern(self, builder):
        """Test UUID replacement in patterns."""
        entry = builder.record_error(
            endpoint="/api/test",
            method="GET",
            status_code=404,
            response_body={"message": "Resource 550e8400-e29b-41d4-a716-446655440000 not found"},
        )

        assert "{id}" in entry.message_pattern
        assert "550e8400" not in entry.message_pattern

    def test_extract_quoted_string_pattern(self, builder):
        """Test quoted string replacement."""
        entry = builder.record_error(
            endpoint="/api/test",
            method="POST",
            status_code=400,
            response_body={"message": 'Field "username" is required'},
        )

        assert '"{value}"' in entry.message_pattern

    def test_extract_number_pattern(self, builder):
        """Test number replacement."""
        entry = builder.record_error(
            endpoint="/api/test",
            method="GET",
            status_code=400,
            response_body={"message": "Maximum of 100 items exceeded"},
        )

        assert "{number}" in entry.message_pattern


class TestBuildCatalog:
    """Test catalog building functionality."""

    def test_build_empty_catalog(self):
        """Test building empty catalog."""
        builder = ErrorCatalogBuilder()
        catalog = builder.build_catalog()

        assert catalog.total_errors == 0
        assert catalog.unique_patterns == 0
        assert catalog.discovered_at != ""

    def test_build_catalog_with_errors(self):
        """Test building catalog with recorded errors."""
        builder = ErrorCatalogBuilder()

        builder.record_error(
            endpoint="/api/users",
            method="GET",
            status_code=401,
            response_body={"message": "Unauthorized"},
        )
        builder.record_error(
            endpoint="/api/users",
            method="POST",
            status_code=400,
            response_body={"message": "Invalid request"},
        )

        catalog = builder.build_catalog()

        assert catalog.total_errors == 2
        assert catalog.unique_patterns == 2
        assert 401 in catalog.errors_by_status
        assert 400 in catalog.errors_by_status

    def test_get_errors_by_status(self):
        """Test getting errors by status code."""
        builder = ErrorCatalogBuilder()

        builder.record_error(
            endpoint="/api/users",
            method="GET",
            status_code=401,
            response_body={"message": "Auth error 1"},
        )
        builder.record_error(
            endpoint="/api/items",
            method="GET",
            status_code=401,
            response_body={"message": "Auth error 2"},
        )

        errors = builder.get_errors_by_status(401)
        assert len(errors) == 2

    def test_clear(self):
        """Test clearing recorded errors."""
        builder = ErrorCatalogBuilder()

        builder.record_error(
            endpoint="/api/test",
            method="GET",
            status_code=500,
            response_body={"message": "Error"},
        )

        assert builder.get_stats()["errors_recorded"] > 0

        builder.clear()

        assert builder.get_stats()["errors_recorded"] == 0
        catalog = builder.build_catalog()
        assert catalog.total_errors == 0


class TestBuilderStatsTracking:
    """Test builder statistics tracking."""

    def test_stats_after_recording(self):
        """Test that stats are updated correctly."""
        builder = ErrorCatalogBuilder()

        builder.record_error(
            endpoint="/api/test",
            method="GET",
            status_code=401,
            response_body={"message": "Unauthorized"},
        )

        stats = builder.get_stats()
        assert stats["errors_recorded"] == 1
        assert stats["patterns_extracted"] == 1
        assert stats["resolutions_generated"] == 1

    def test_stats_deduplication(self):
        """Test deduplication is tracked in stats."""
        builder = ErrorCatalogBuilder()

        # Same error twice
        builder.record_error(
            endpoint="/api/test",
            method="GET",
            status_code=401,
            response_body={"message": "Unauthorized"},
        )
        builder.record_error(
            endpoint="/api/test",
            method="GET",
            status_code=401,
            response_body={"message": "Unauthorized"},
        )

        stats = builder.get_stats()
        assert stats["errors_recorded"] == 2
        assert stats["errors_deduplicated"] == 1

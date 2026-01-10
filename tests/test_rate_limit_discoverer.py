# Copyright (c) 2026 Robin Mordasiewicz. MIT License.

"""Unit tests for RateLimitDiscoverer module.

Tests rate limit discovery functionality including configuration,
header parsing, and limit discovery.
"""

import pytest

from scripts.discovery.rate_limit_discoverer import (
    DiscovererStats,
    ProbeResult,
    RateLimitDiscoverer,
    RateLimitDiscoveryConfig,
    RateLimitInfo,
    parse_rate_limit_headers,
)


class TestRateLimitDiscoveryConfig:
    """Test RateLimitDiscoveryConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = RateLimitDiscoveryConfig()
        assert config.enabled is False  # Opt-in only
        assert config.max_probe_rate == 20
        assert config.probe_delay_seconds == 0.1
        assert config.cooldown_seconds == 60.0
        assert config.safe_mode is True

    def test_custom_values(self):
        """Test custom configuration values."""
        config = RateLimitDiscoveryConfig(
            enabled=True,
            max_probe_rate=50,
            probe_delay_seconds=0.05,
            cooldown_seconds=30.0,
            safe_mode=False,
        )
        assert config.enabled is True
        assert config.max_probe_rate == 50
        assert config.probe_delay_seconds == 0.05
        assert config.safe_mode is False


class TestRateLimitInfo:
    """Test RateLimitInfo dataclass."""

    def test_default_values(self):
        """Test default info values."""
        info = RateLimitInfo()
        assert info.endpoint == ""
        assert info.method == "GET"
        assert info.requests_per_minute is None
        assert info.discovered_at is None
        assert info.confidence == "unknown"

    def test_to_dict(self):
        """Test to_dict method."""
        info = RateLimitInfo(
            endpoint="/api/test",
            method="POST",
            requests_per_minute=100,
            burst_limit=10,
            retry_after_header=True,
            retry_after_value=60.0,
            discovered_at="2024-01-01T00:00:00Z",
            confidence="high",
        )
        result = info.to_dict()

        assert result["endpoint"] == "/api/test"
        assert result["method"] == "POST"
        assert result["requests_per_minute"] == 100
        assert result["burst_limit"] == 10
        assert result["retry_after_header"] is True
        assert result["confidence"] == "high"

    def test_to_dict_optional_fields(self):
        """Test to_dict omits None values."""
        info = RateLimitInfo(
            endpoint="/api/test",
            method="GET",
            discovered_at="2024-01-01T00:00:00Z",
            confidence="low",
        )
        result = info.to_dict()

        assert "requests_per_minute" not in result
        assert "burst_limit" not in result
        assert "retry_after_header" not in result

    def test_to_extension(self):
        """Test to_extension method for OpenAPI output."""
        info = RateLimitInfo(
            endpoint="/api/test",
            method="GET",
            requests_per_minute=100,
            requests_per_second=1.67,
            burst_limit=10,
            retry_after_header=True,
            discovered_at="2024-01-01T00:00:00Z",
        )
        result = info.to_extension()

        assert result["requests_per_minute"] == 100
        assert result["burst_limit"] == 10
        assert result["retry_after_header"] is True
        assert result["discovered_at"] == "2024-01-01T00:00:00Z"
        # Should not include internal fields
        assert "endpoint" not in result
        assert "method" not in result
        assert "confidence" not in result


class TestDiscovererStats:
    """Test DiscovererStats dataclass."""

    def test_default_values(self):
        """Test default stats values."""
        stats = DiscovererStats()
        assert stats.endpoints_probed == 0
        assert stats.requests_made == 0
        assert stats.rate_limits_hit == 0
        assert stats.limits_discovered == 0
        assert stats.skipped_disabled == 0

    def test_to_dict(self):
        """Test to_dict method."""
        stats = DiscovererStats(
            endpoints_probed=5,
            requests_made=100,
            rate_limits_hit=3,
            limits_discovered=2,
            skipped_disabled=1,
        )
        result = stats.to_dict()

        assert result["endpoints_probed"] == 5
        assert result["requests_made"] == 100
        assert result["rate_limits_hit"] == 3


class TestProbeResult:
    """Test ProbeResult dataclass."""

    def test_basic_result(self):
        """Test basic probe result."""
        result = ProbeResult(
            status_code=200,
            response_time_ms=50.0,
        )
        assert result.status_code == 200
        assert result.response_time_ms == 50.0
        assert result.retry_after is None

    def test_rate_limit_result(self):
        """Test probe result with rate limit info."""
        result = ProbeResult(
            status_code=429,
            response_time_ms=10.0,
            retry_after=60.0,
            rate_limit_remaining=0,
            rate_limit_limit=100,
        )
        assert result.status_code == 429
        assert result.retry_after == 60.0
        assert result.rate_limit_remaining == 0
        assert result.rate_limit_limit == 100


class TestRateLimitDiscovererInitialization:
    """Test RateLimitDiscoverer initialization."""

    def test_default_config(self):
        """Test initialization with default config."""
        discoverer = RateLimitDiscoverer()
        assert discoverer.config.enabled is False
        assert discoverer.config.max_probe_rate == 20
        assert discoverer.is_enabled() is False

    def test_dict_config(self):
        """Test initialization with dict config."""
        config = {
            "enabled": True,
            "max_probe_rate": 30,
            "safe_mode": False,
        }
        discoverer = RateLimitDiscoverer(config=config)
        assert discoverer.config.enabled is True
        assert discoverer.config.max_probe_rate == 30
        assert discoverer.is_enabled() is True

    def test_config_object(self):
        """Test initialization with RateLimitDiscoveryConfig object."""
        config = RateLimitDiscoveryConfig(enabled=True)
        discoverer = RateLimitDiscoverer(config=config)
        assert discoverer.is_enabled() is True


class TestRateLimitDiscoverLimits:
    """Test rate limit discovery functionality."""

    @pytest.mark.asyncio
    async def test_discover_limits_disabled(self):
        """Test that disabled discoverer returns unknown confidence."""
        discoverer = RateLimitDiscoverer(config={"enabled": False})

        async def mock_request():
            return ProbeResult(status_code=200, response_time_ms=50.0)

        result = await discoverer.discover_limits("/api/test", mock_request)

        assert result.confidence == "unknown"
        stats = discoverer.get_stats()
        assert stats["skipped_disabled"] == 1
        assert stats["endpoints_probed"] == 0

    @pytest.mark.asyncio
    async def test_discover_limits_no_rate_limit(self):
        """Test discovery when no rate limit is hit."""
        discoverer = RateLimitDiscoverer(
            config={
                "enabled": True,
                "max_probe_rate": 5,
                "probe_delay_seconds": 0.01,
            },
        )

        async def mock_request():
            return ProbeResult(status_code=200, response_time_ms=50.0)

        result = await discoverer.discover_limits("/api/test", mock_request)

        # Confidence is low because we didn't hit the limit
        assert result.confidence == "low"
        assert result.endpoint == "/api/test"
        stats = discoverer.get_stats()
        assert stats["requests_made"] == 5

    @pytest.mark.asyncio
    async def test_discover_limits_hits_rate_limit(self):
        """Test discovery when rate limit is hit."""
        discoverer = RateLimitDiscoverer(
            config={
                "enabled": True,
                "max_probe_rate": 10,
                "probe_delay_seconds": 0.01,
                "safe_mode": True,
            },
        )

        call_count = 0

        async def mock_request():
            nonlocal call_count
            call_count += 1
            if call_count > 3:
                return ProbeResult(status_code=429, response_time_ms=10.0, retry_after=60.0)
            return ProbeResult(status_code=200, response_time_ms=50.0)

        result = await discoverer.discover_limits("/api/test", mock_request)

        # Should stop at first 429 in safe mode
        assert call_count == 4
        assert result.retry_after_header is True
        stats = discoverer.get_stats()
        assert stats["rate_limits_hit"] == 1

    @pytest.mark.asyncio
    async def test_discover_limits_with_headers(self):
        """Test discovery with rate limit headers."""
        discoverer = RateLimitDiscoverer(
            config={
                "enabled": True,
                "max_probe_rate": 3,
                "probe_delay_seconds": 0.01,
            },
        )

        async def mock_request():
            return ProbeResult(
                status_code=200,
                response_time_ms=50.0,
                rate_limit_limit=100,
                rate_limit_remaining=95,
            )

        result = await discoverer.discover_limits("/api/test", mock_request)

        assert result.requests_per_minute == 100
        assert result.rate_limit_header == "X-RateLimit-Limit"


class TestRateLimitDiscoverFromHeaders:
    """Test header-only rate limit discovery."""

    @pytest.mark.asyncio
    async def test_discover_from_headers(self):
        """Test discovering rate limits from headers."""
        discoverer = RateLimitDiscoverer()

        async def mock_request():
            return ProbeResult(
                status_code=200,
                response_time_ms=50.0,
                headers={
                    "X-RateLimit-Limit": "1000",
                    "X-RateLimit-Remaining": "950",
                },
            )

        result = await discoverer.discover_from_headers("/api/test", mock_request)

        assert result.requests_per_minute == 1000
        assert result.rate_limit_header == "X-RateLimit-Limit"
        assert result.confidence == "high"

    @pytest.mark.asyncio
    async def test_discover_from_headers_429(self):
        """Test discovering from 429 response headers."""
        discoverer = RateLimitDiscoverer()

        async def mock_request():
            return ProbeResult(
                status_code=429,
                response_time_ms=10.0,
                headers={
                    "Retry-After": "60",
                },
            )

        result = await discoverer.discover_from_headers("/api/test", mock_request)

        assert result.retry_after_header is True
        assert result.retry_after_value == 60.0
        stats = discoverer.get_stats()
        assert stats["rate_limits_hit"] == 1


class TestParseRateLimitHeaders:
    """Test parse_rate_limit_headers convenience function."""

    def test_parse_standard_headers(self):
        """Test parsing standard rate limit headers."""
        headers = {
            "X-RateLimit-Limit": "1000",
            "X-RateLimit-Remaining": "950",
            "X-RateLimit-Reset": "1609459200",
        }
        result = parse_rate_limit_headers(headers)

        assert result["limit"] == 1000
        assert result["remaining"] == 950
        assert result["reset"] == 1609459200

    def test_parse_retry_after(self):
        """Test parsing Retry-After header."""
        headers = {"Retry-After": "60"}
        result = parse_rate_limit_headers(headers)

        assert result["retry_after"] == 60.0

    def test_parse_case_insensitive(self):
        """Test that header parsing is case-insensitive."""
        headers = {
            "x-ratelimit-limit": "500",
            "RETRY-AFTER": "30",
        }
        result = parse_rate_limit_headers(headers)

        assert result["limit"] == 500
        assert result["retry_after"] == 30.0

    def test_parse_invalid_values(self):
        """Test parsing with invalid values."""
        headers = {
            "X-RateLimit-Limit": "not-a-number",
            "Retry-After": "invalid",
        }
        result = parse_rate_limit_headers(headers)

        # Invalid values should not be included or kept as strings
        assert "limit" not in result
        assert result.get("retry_after") == "invalid"

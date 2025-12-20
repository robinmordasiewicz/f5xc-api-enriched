"""Async rate limiter with exponential backoff.

Provides rate limiting for API discovery to avoid throttling.
Uses token bucket algorithm with configurable backoff.
"""

import asyncio
import time
from dataclasses import dataclass


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    requests_per_second: float = 5.0
    burst_limit: int = 10
    backoff_base: float = 1.0
    backoff_max: float = 60.0
    backoff_multiplier: float = 2.0
    retry_attempts: int = 3


@dataclass
class RateLimiterStats:
    """Statistics for rate limiter."""

    requests_made: int = 0
    requests_delayed: int = 0
    total_wait_time: float = 0.0
    rate_limit_hits: int = 0
    retries: int = 0


class RateLimiter:
    """Async rate limiter using token bucket algorithm.

    Provides:
    - Token bucket rate limiting
    - Semaphore for concurrent request limiting
    - Exponential backoff on rate limit responses
    - Statistics tracking
    """

    def __init__(self, config: RateLimitConfig | dict | None = None) -> None:
        """Initialize rate limiter.

        Args:
            config: Rate limit configuration (RateLimitConfig, dict, or None for defaults)
        """
        if config is None:
            self.config = RateLimitConfig()
        elif isinstance(config, dict):
            self.config = RateLimitConfig(
                requests_per_second=config.get("requests_per_second", 5.0),
                burst_limit=config.get("burst_limit", 10),
                backoff_base=config.get("backoff_base", 1.0),
                backoff_max=config.get("backoff_max", 60.0),
                backoff_multiplier=config.get("backoff_multiplier", 2.0),
                retry_attempts=config.get("retry_attempts", 3),
            )
        else:
            self.config = config

        # Token bucket state
        self._tokens = float(self.config.burst_limit)
        self._last_update = time.monotonic()
        self._lock = asyncio.Lock()

        # Concurrent request limiting
        self._semaphore = asyncio.Semaphore(self.config.burst_limit)

        # Statistics
        self.stats = RateLimiterStats()

        # Current backoff state
        self._current_backoff = self.config.backoff_base

    async def acquire(self) -> None:
        """Acquire permission to make a request.

        Blocks until a token is available and semaphore is acquired.
        """
        # Wait for semaphore (concurrent request limit)
        await self._semaphore.acquire()

        # Wait for token (rate limit)
        async with self._lock:
            await self._wait_for_token()
            self.stats.requests_made += 1

    def release(self) -> None:
        """Release the semaphore after request completion."""
        self._semaphore.release()

    async def _wait_for_token(self) -> None:
        """Wait until a token is available in the bucket."""
        while True:
            self._refill_tokens()

            if self._tokens >= 1:
                self._tokens -= 1
                return

            # Calculate wait time until next token
            tokens_needed = 1 - self._tokens
            wait_time = tokens_needed / self.config.requests_per_second

            self.stats.requests_delayed += 1
            self.stats.total_wait_time += wait_time

            await asyncio.sleep(wait_time)

    def _refill_tokens(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_update
        self._last_update = now

        # Add tokens based on elapsed time
        new_tokens = elapsed * self.config.requests_per_second
        self._tokens = min(self._tokens + new_tokens, float(self.config.burst_limit))

    async def handle_rate_limit_response(self, retry_after: float | None = None) -> bool:
        """Handle a rate limit response (429 status).

        Args:
            retry_after: Optional Retry-After header value in seconds

        Returns:
            True if should retry, False if max retries exceeded
        """
        self.stats.rate_limit_hits += 1

        # Determine wait time
        if retry_after is not None:
            wait_time = retry_after
        else:
            wait_time = self._current_backoff
            # Increase backoff for next time
            self._current_backoff = min(
                self._current_backoff * self.config.backoff_multiplier,
                self.config.backoff_max,
            )

        # Check if we should retry
        if self.stats.retries >= self.config.retry_attempts:
            return False

        self.stats.retries += 1
        self.stats.total_wait_time += wait_time

        await asyncio.sleep(wait_time)
        return True

    def reset_backoff(self) -> None:
        """Reset backoff to base value after successful request."""
        self._current_backoff = self.config.backoff_base

    def reset_retries(self) -> None:
        """Reset retry counter after successful request."""
        self.stats.retries = 0

    async def __aenter__(self) -> "RateLimiter":
        """Async context manager entry."""
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        self.release()
        if exc_type is None:
            self.reset_backoff()
            self.reset_retries()

    def get_stats(self) -> dict:
        """Get current statistics as a dictionary."""
        return {
            "requests_made": self.stats.requests_made,
            "requests_delayed": self.stats.requests_delayed,
            "total_wait_time_seconds": round(self.stats.total_wait_time, 2),
            "rate_limit_hits": self.stats.rate_limit_hits,
            "retries": self.stats.retries,
            "avg_wait_per_request": (
                round(self.stats.total_wait_time / self.stats.requests_made, 3)
                if self.stats.requests_made > 0
                else 0
            ),
        }

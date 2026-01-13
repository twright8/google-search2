"""Async Google Custom Search API client with proper rate limiting."""

import asyncio
import time
from typing import AsyncIterator

import aiohttp


class TokenBucketRateLimiter:
    """
    Token bucket rate limiter for API requests.

    Enforces both per-minute and per-day limits by tracking tokens
    that replenish over time.
    """

    def __init__(
        self,
        requests_per_minute: int = 100,
        requests_per_day: int = 10000,
    ):
        self.requests_per_minute = requests_per_minute
        self.requests_per_day = requests_per_day

        # Token buckets
        self._minute_tokens = float(requests_per_minute)
        self._day_tokens = float(requests_per_day)

        # Last refill timestamps
        self._last_minute_refill = time.monotonic()
        self._last_day_refill = time.monotonic()

        # Lock for thread-safe token management
        self._lock = asyncio.Lock()

        # Track for reporting
        self._total_requests = 0
        self._requests_today = 0
        self._day_start = time.monotonic()

    def _refill_tokens(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()

        # Refill minute tokens (rate: requests_per_minute / 60 per second)
        minute_elapsed = now - self._last_minute_refill
        minute_refill = minute_elapsed * (self.requests_per_minute / 60.0)
        self._minute_tokens = min(
            self.requests_per_minute,
            self._minute_tokens + minute_refill
        )
        self._last_minute_refill = now

        # Refill day tokens (rate: requests_per_day / 86400 per second)
        day_elapsed = now - self._last_day_refill
        day_refill = day_elapsed * (self.requests_per_day / 86400.0)
        self._day_tokens = min(
            self.requests_per_day,
            self._day_tokens + day_refill
        )
        self._last_day_refill = now

        # Reset daily counter if 24 hours passed
        if now - self._day_start >= 86400:
            self._requests_today = 0
            self._day_start = now

    async def acquire(self) -> None:
        """
        Acquire a token, waiting if necessary.

        Blocks until both minute and day limits allow a request.
        """
        async with self._lock:
            while True:
                self._refill_tokens()

                # Check if we have tokens available
                if self._minute_tokens >= 1.0 and self._day_tokens >= 1.0:
                    self._minute_tokens -= 1.0
                    self._day_tokens -= 1.0
                    self._total_requests += 1
                    self._requests_today += 1
                    return

                # Calculate wait time
                if self._minute_tokens < 1.0:
                    # Wait for minute token
                    tokens_needed = 1.0 - self._minute_tokens
                    wait_time = tokens_needed / (self.requests_per_minute / 60.0)
                else:
                    # Wait for day token (shouldn't happen often)
                    tokens_needed = 1.0 - self._day_tokens
                    wait_time = tokens_needed / (self.requests_per_day / 86400.0)

                # Release lock while waiting
                self._lock.release()
                try:
                    await asyncio.sleep(min(wait_time, 1.0))  # Cap at 1 second
                finally:
                    await self._lock.acquire()

    @property
    def stats(self) -> dict:
        """Get current rate limiter statistics."""
        return {
            "total_requests": self._total_requests,
            "requests_today": self._requests_today,
            "minute_tokens_available": self._minute_tokens,
            "day_tokens_available": self._day_tokens,
        }


class RateLimitExceeded(Exception):
    """Raised when rate limit would be exceeded."""
    pass


class AsyncGoogleSearch:
    """Async client for Google Custom Search API with rate limiting."""

    BASE_URL = "https://www.googleapis.com/customsearch/v1"

    def __init__(
        self,
        api_key: str,
        cx: str,
        rate_limit_per_min: int = 100,
        rate_limit_per_day: int = 10000,
        max_results_per_query: int = 10,
        max_concurrent: int = 10,
        retry_max: int = 3,
        retry_base_delay: float = 1.0,
        retry_max_delay: float = 30.0,
    ):
        self.api_key = api_key
        self.cx = cx
        self.max_results_per_query = max_results_per_query

        # Retry settings
        self.retry_max = retry_max
        self.retry_base_delay = retry_base_delay
        self.retry_max_delay = retry_max_delay

        # Proper rate limiter (tokens over time)
        self._rate_limiter = TokenBucketRateLimiter(
            requests_per_minute=rate_limit_per_min,
            requests_per_day=rate_limit_per_day,
        )

        # Concurrency limiter (parallel requests)
        self._semaphore = asyncio.Semaphore(max_concurrent)

        # Reusable session (created lazily)
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create the shared aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """Close the shared session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def __aenter__(self) -> "AsyncGoogleSearch":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()

    async def search(self, query: str, num_results: int | None = None) -> list[dict]:
        """
        Execute a single search query with retry logic.

        Args:
            query: Search query string
            num_results: Number of results (default: max_results_per_query)

        Returns:
            List of result items with 'title', 'link', 'snippet'

        Raises:
            aiohttp.ClientResponseError: On non-retryable errors (4xx)
            aiohttp.ClientError: On network errors after all retries exhausted
        """
        if num_results is None:
            num_results = self.max_results_per_query

        # Wait for rate limit token
        await self._rate_limiter.acquire()

        # Limit concurrent requests
        async with self._semaphore:
            session = await self._get_session()
            params = {
                "key": self.api_key,
                "cx": self.cx,
                "q": query,
                "num": min(num_results, 10),  # API max is 10
            }

            last_exception: Exception | None = None
            for attempt in range(self.retry_max + 1):
                try:
                    async with session.get(self.BASE_URL, params=params) as response:
                        # Don't retry client errors (4xx) - these are not transient
                        if 400 <= response.status < 500:
                            response.raise_for_status()

                        # Retry server errors (5xx)
                        if response.status >= 500:
                            raise aiohttp.ClientResponseError(
                                response.request_info,
                                response.history,
                                status=response.status,
                                message=f"Server error {response.status}",
                            )

                        response.raise_for_status()
                        data = await response.json()
                        return data.get("items", [])

                except aiohttp.ClientResponseError as e:
                    # Don't retry 4xx errors - they're not transient
                    if e.status is not None and 400 <= e.status < 500:
                        raise
                    last_exception = e
                    if attempt < self.retry_max:
                        delay = min(
                            self.retry_base_delay * (2 ** attempt),
                            self.retry_max_delay,
                        )
                        await asyncio.sleep(delay)
                    else:
                        raise

                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    last_exception = e
                    if attempt < self.retry_max:
                        delay = min(
                            self.retry_base_delay * (2 ** attempt),
                            self.retry_max_delay,
                        )
                        await asyncio.sleep(delay)
                    else:
                        raise

            # Should not reach here, but satisfy type checker
            if last_exception:
                raise last_exception
            return []

    async def search_many(
        self,
        queries: list[str],
        num_results: int | None = None,
    ) -> AsyncIterator[str]:
        """
        Execute multiple searches and yield URLs as they complete.

        Args:
            queries: List of search query strings
            num_results: Results per query

        Yields:
            URLs from search results
        """
        tasks = [self.search(q, num_results) for q in queries]

        for coro in asyncio.as_completed(tasks):
            items = await coro
            for item in items:
                if "link" in item:
                    yield item["link"]

    @property
    def rate_limit_stats(self) -> dict:
        """Get current rate limiter statistics."""
        return self._rate_limiter.stats

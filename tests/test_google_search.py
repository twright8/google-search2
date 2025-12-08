import pytest
import asyncio
import time
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_search_returns_items():
    """Search should return list of items from API response."""
    from src.google_search import AsyncGoogleSearch

    mock_response = {
        "items": [
            {"title": "Result 1", "link": "https://example1.com", "snippet": "..."},
            {"title": "Result 2", "link": "https://example2.com", "snippet": "..."},
        ]
    }

    with patch("aiohttp.ClientSession") as mock_session_class:
        mock_session = AsyncMock()
        mock_response_obj = AsyncMock()
        mock_response_obj.json = AsyncMock(return_value=mock_response)
        mock_response_obj.raise_for_status = MagicMock()
        mock_session.get = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response_obj)))
        mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_class.return_value.__aexit__ = AsyncMock()

        client = AsyncGoogleSearch(api_key="test", cx="test_cx")
        results = await client.search("python")

        assert len(results) == 2
        assert results[0]["link"] == "https://example1.com"


@pytest.mark.asyncio
async def test_search_many_yields_urls():
    """search_many should yield URLs from multiple queries."""
    from src.google_search import AsyncGoogleSearch

    client = AsyncGoogleSearch(api_key="test", cx="test_cx")

    # Mock the search method directly
    async def mock_search(query, num_results=10):
        return [{"link": f"https://{query}.com/1"}, {"link": f"https://{query}.com/2"}]

    client.search = mock_search

    urls = []
    async for url in client.search_many(["python", "rust"]):
        urls.append(url)

    assert len(urls) == 4
    assert "https://python.com/1" in urls
    assert "https://rust.com/2" in urls


@pytest.mark.asyncio
async def test_token_bucket_rate_limiter_allows_burst():
    """Rate limiter should allow burst up to limit."""
    from src.google_search import TokenBucketRateLimiter

    limiter = TokenBucketRateLimiter(requests_per_minute=10, requests_per_day=1000)

    # Should allow 10 immediate requests (burst)
    for _ in range(10):
        await limiter.acquire()

    assert limiter.stats["total_requests"] == 10


@pytest.mark.asyncio
async def test_token_bucket_rate_limiter_blocks_when_exhausted():
    """Rate limiter should block when tokens exhausted."""
    from src.google_search import TokenBucketRateLimiter

    limiter = TokenBucketRateLimiter(requests_per_minute=5, requests_per_day=1000)

    # Exhaust all tokens
    for _ in range(5):
        await limiter.acquire()

    # Next acquire should take time (tokens need to refill)
    start = time.monotonic()
    await limiter.acquire()
    elapsed = time.monotonic() - start

    # Should have waited ~0.2 seconds (1 token / 5 per min = 12 sec per token)
    # Actually: 5/60 = 0.083 tokens/sec, so 1 token = 12 seconds
    # But we cap wait at 1 second per iteration, so it should be quick
    assert elapsed > 0.01  # Some wait occurred
    assert limiter.stats["total_requests"] == 6


@pytest.mark.asyncio
async def test_rate_limiter_stats():
    """Rate limiter should track statistics."""
    from src.google_search import TokenBucketRateLimiter

    limiter = TokenBucketRateLimiter(requests_per_minute=100, requests_per_day=10000)

    await limiter.acquire()
    await limiter.acquire()

    stats = limiter.stats
    assert stats["total_requests"] == 2
    assert stats["requests_today"] == 2
    assert stats["minute_tokens_available"] < 100
    assert stats["day_tokens_available"] < 10000

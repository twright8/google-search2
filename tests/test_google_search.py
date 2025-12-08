import pytest
import asyncio
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

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_pipeline_yields_results():
    """Pipeline should yield CrawlOutput for each URL."""
    from src.pipeline import run_pipeline
    from src.crawler import CrawlOutput

    # Mock Google Search client
    mock_google = MagicMock()
    async def mock_search_many(queries):
        for q in queries:
            yield f"https://{q}.com"
    mock_google.search_many = mock_search_many

    # Mock Crawler
    mock_crawler = MagicMock()
    async def mock_crawl_urls(urls, use_raw_markdown=False):
        for url in urls:
            yield CrawlOutput(
                url=url,
                success=True,
                content=f"Content from {url}",
                error=None,
            )
    mock_crawler.crawl_urls = mock_crawl_urls

    results = []
    async for output in run_pipeline(
        queries=["python", "rust"],
        google_client=mock_google,
        crawler=mock_crawler,
    ):
        results.append(output)

    assert len(results) == 2
    assert all(r.success for r in results)
    assert "https://python.com" in [r.url for r in results]


@pytest.mark.asyncio
async def test_pipeline_handles_failures():
    """Pipeline should yield failed results with error info."""
    from src.pipeline import run_pipeline
    from src.crawler import CrawlOutput

    mock_google = MagicMock()
    async def mock_search_many(queries):
        yield "https://fail.com"
    mock_google.search_many = mock_search_many

    mock_crawler = MagicMock()
    async def mock_crawl_urls(urls, use_raw_markdown=False):
        yield CrawlOutput(
            url="https://fail.com",
            success=False,
            content=None,
            error="Connection timeout",
        )
    mock_crawler.crawl_urls = mock_crawl_urls

    results = []
    async for output in run_pipeline(
        queries=["fail"],
        google_client=mock_google,
        crawler=mock_crawler,
    ):
        results.append(output)

    assert len(results) == 1
    assert results[0].success is False
    assert results[0].error == "Connection timeout"

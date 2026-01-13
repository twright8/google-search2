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


@pytest.mark.asyncio
async def test_pipeline_deduplicates_urls():
    """Pipeline should deduplicate URLs from multiple search queries."""
    from src.pipeline import run_pipeline
    from src.crawler import CrawlOutput

    # Mock Google Search that returns duplicate URLs
    mock_google = MagicMock()
    async def mock_search_many(queries):
        # Simulate overlapping results from different queries
        yield "https://common.com"      # From query 1
        yield "https://unique1.com"     # From query 1
        yield "https://common.com"      # Duplicate from query 2
        yield "https://unique2.com"     # From query 2
        yield "https://common.com"      # Another duplicate
    mock_google.search_many = mock_search_many

    # Track which URLs the crawler receives
    crawled_urls = []
    mock_crawler = MagicMock()
    async def mock_crawl_urls(urls, use_raw_markdown=False):
        crawled_urls.extend(urls)
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
        queries=["query1", "query2"],
        google_client=mock_google,
        crawler=mock_crawler,
    ):
        results.append(output)

    # Should only crawl 3 unique URLs
    assert len(crawled_urls) == 3
    assert crawled_urls.count("https://common.com") == 1
    assert "https://unique1.com" in crawled_urls
    assert "https://unique2.com" in crawled_urls

    # Results should also be 3
    assert len(results) == 3

"""Streamlined pipeline orchestration.

Optimized for throughput by:
1. Collecting all URLs from Google Search first
2. Single arun_many call to Crawl4AI (no batching overhead)
3. Streaming results as they complete
"""

from typing import AsyncIterator, Protocol

from src.crawler import CrawlOutput


class GoogleSearchProtocol(Protocol):
    """Protocol for Google Search client."""

    def search_many(self, queries: list[str]) -> AsyncIterator[str]: ...

    async def close(self) -> None: ...


class CrawlerProtocol(Protocol):
    """Protocol for content crawler."""

    async def __aenter__(self) -> "CrawlerProtocol": ...

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None: ...

    def crawl_urls(
        self,
        urls: list[str],
        use_raw_markdown: bool = False,
    ) -> AsyncIterator[CrawlOutput]: ...


async def run_pipeline(
    queries: list[str],
    google_client: GoogleSearchProtocol,
    crawler: CrawlerProtocol,
    use_raw_markdown: bool = False,
    queue_size: int = 100,  # Kept for API compatibility
    batch_size: int = 10,   # Kept for API compatibility
) -> AsyncIterator[CrawlOutput]:
    """
    Run the full search-to-crawl pipeline.

    Optimized architecture:
    1. Collect all URLs from Google Search (parallel queries)
    2. Single arun_many() call with all URLs (Crawl4AI handles concurrency)
    3. Stream results as pages complete

    Args:
        queries: Search queries to execute
        google_client: Async Google Search client
        crawler: Content crawler (use as context manager for best performance)
        use_raw_markdown: If True, return raw markdown
        queue_size: Deprecated, kept for compatibility
        batch_size: Deprecated, kept for compatibility

    Yields:
        CrawlOutput for each crawled URL
    """
    # Phase 1: Collect all URLs from Google Search (deduplicated)
    seen_urls: set[str] = set()
    urls: list[str] = []
    async for url in google_client.search_many(queries):
        if url not in seen_urls:
            seen_urls.add(url)
            urls.append(url)

    if not urls:
        return

    # Phase 2: Crawl all URLs in single arun_many call (streaming)
    # Crawl4AI's MemoryAdaptiveDispatcher handles concurrency internally
    async for output in crawler.crawl_urls(urls, use_raw_markdown):
        yield output

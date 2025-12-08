"""Queue-based streaming pipeline orchestration."""

import asyncio
from typing import AsyncIterator, Protocol

from src.crawler import CrawlOutput


class GoogleSearchProtocol(Protocol):
    """Protocol for Google Search client."""

    def search_many(self, queries: list[str]) -> AsyncIterator[str]: ...


class CrawlerProtocol(Protocol):
    """Protocol for content crawler."""

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
    queue_size: int = 100,
    batch_size: int = 10,
) -> AsyncIterator[CrawlOutput]:
    """
    Run the full search-to-crawl pipeline with queue-based streaming.

    Args:
        queries: Search queries to execute
        google_client: Async Google Search client
        crawler: Content crawler
        use_raw_markdown: If True, return raw markdown
        queue_size: Max URLs in queue (backpressure)
        batch_size: URLs per crawl batch

    Yields:
        CrawlOutput for each crawled URL
    """
    url_queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=queue_size)
    results_queue: asyncio.Queue[CrawlOutput | None] = asyncio.Queue()

    async def producer():
        """Feed URLs from Google Search into queue."""
        try:
            async for url in google_client.search_many(queries):
                await url_queue.put(url)
        finally:
            await url_queue.put(None)  # Sentinel

    async def consumer():
        """Consume URLs, crawl in batches, push results."""
        urls_batch: list[str] = []

        while True:
            url = await url_queue.get()

            if url is None:
                # Process remaining batch
                if urls_batch:
                    async for output in crawler.crawl_urls(urls_batch, use_raw_markdown):
                        await results_queue.put(output)
                break

            urls_batch.append(url)

            # Process when batch is full or queue is empty
            if len(urls_batch) >= batch_size or url_queue.empty():
                async for output in crawler.crawl_urls(urls_batch, use_raw_markdown):
                    await results_queue.put(output)
                urls_batch.clear()

        await results_queue.put(None)  # Sentinel

    # Start producer and consumer
    producer_task = asyncio.create_task(producer())
    consumer_task = asyncio.create_task(consumer())

    # Yield results as they arrive
    while True:
        output = await results_queue.get()
        if output is None:
            break
        yield output

    # Ensure tasks complete
    await producer_task
    await consumer_task

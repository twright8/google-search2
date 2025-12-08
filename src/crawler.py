"""Crawl4AI wrapper for content extraction."""

from dataclasses import dataclass
from typing import AsyncIterator

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.async_dispatcher import MemoryAdaptiveDispatcher, RateLimiter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from crawl4ai.content_filter_strategy import PruningContentFilter

from src.config import CrawlerConfig


@dataclass
class CrawlOutput:
    """Result from crawling a single URL."""

    url: str
    success: bool
    content: str | None
    error: str | None


class ContentCrawler:
    """Wrapper around Crawl4AI for content extraction."""

    def __init__(self, config: CrawlerConfig):
        self.config = config

    def _build_browser_config(self) -> BrowserConfig:
        """Build browser configuration."""
        return BrowserConfig(
            headless=self.config.headless,
            verbose=False,
        )

    def _build_run_config(self, use_raw_markdown: bool = False) -> CrawlerRunConfig:
        """Build crawler run configuration."""
        if self.config.use_pruning_filter and not use_raw_markdown:
            content_filter = PruningContentFilter(
                threshold=self.config.pruning_threshold,
                threshold_type="fixed",
            )
            md_generator = DefaultMarkdownGenerator(content_filter=content_filter)
        else:
            md_generator = DefaultMarkdownGenerator()

        return CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            markdown_generator=md_generator,
        )

    def _build_dispatcher(self) -> MemoryAdaptiveDispatcher:
        """Build dispatcher with rate limiting."""
        rate_limiter = RateLimiter(
            base_delay=(
                self.config.retry_base_delay_min,
                self.config.retry_base_delay_max,
            ),
            max_delay=self.config.retry_max_delay,
            max_retries=self.config.retry_max,
        )

        return MemoryAdaptiveDispatcher(
            memory_threshold_percent=self.config.memory_threshold_percent,
            max_session_permit=self.config.max_concurrency,
            rate_limiter=rate_limiter,
        )

    async def crawl_urls(
        self,
        urls: list[str],
        use_raw_markdown: bool = False,
    ) -> AsyncIterator[CrawlOutput]:
        """
        Crawl URLs and yield results as they complete.

        Args:
            urls: List of URLs to crawl
            use_raw_markdown: If True, return raw_markdown; else fit_markdown

        Yields:
            CrawlOutput for each URL
        """
        if not urls:
            return

        browser_config = self._build_browser_config()
        run_config = self._build_run_config(use_raw_markdown)
        dispatcher = self._build_dispatcher()

        async with AsyncWebCrawler(config=browser_config) as crawler:
            results = await crawler.arun_many(
                urls=urls,
                config=run_config,
                dispatcher=dispatcher,
            )

            for result in results:
                if result.success:
                    if use_raw_markdown:
                        content = result.markdown.raw_markdown
                    else:
                        content = (
                            result.markdown.fit_markdown
                            or result.markdown.raw_markdown
                        )
                    yield CrawlOutput(
                        url=result.url,
                        success=True,
                        content=content,
                        error=None,
                    )
                else:
                    yield CrawlOutput(
                        url=result.url,
                        success=False,
                        content=None,
                        error=result.error_message,
                    )

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
    """Wrapper around Crawl4AI for content extraction.

    Supports context manager for persistent browser session:
        async with ContentCrawler(config) as crawler:
            async for result in crawler.crawl_urls(urls):
                ...
    """

    def __init__(self, config: CrawlerConfig):
        self.config = config
        self._crawler: AsyncWebCrawler | None = None

    async def __aenter__(self) -> "ContentCrawler":
        """Start browser session."""
        browser_config = self._build_browser_config()
        self._crawler = AsyncWebCrawler(config=browser_config)
        await self._crawler.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Close browser session."""
        if self._crawler:
            await self._crawler.__aexit__(exc_type, exc_val, exc_tb)
            self._crawler = None

    def _build_browser_config(self) -> BrowserConfig:
        """Build browser configuration with anti-bot protection."""
        extra_args = []
        if self.config.browser_type == "undetected":
            extra_args = [
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor",
            ]

        return BrowserConfig(
            browser_type=self.config.browser_type,
            headless=self.config.headless,
            enable_stealth=self.config.enable_stealth,
            extra_args=extra_args,
            verbose=False,
        )

    # Common cookie consent button selectors
    COOKIE_CONSENT_JS = """
        (function() {
            const selectors = [
                '[id*="cookie"] button[id*="accept"]',
                '[id*="cookie"] button[id*="agree"]',
                '[class*="cookie"] button[class*="accept"]',
                '[class*="cookie"] button[class*="agree"]',
                '[id*="consent"] button[id*="accept"]',
                '[class*="consent"] button[class*="accept"]',
                '#onetrust-accept-btn-handler',
                '.cc-accept', '.cc-btn.cc-allow',
                '[data-testid*="cookie-accept"]',
                '[data-testid*="accept-cookies"]',
                '[aria-label*="accept cookies" i]',
                '[aria-label*="agree" i]',
                'button[title*="Accept" i]',
                '.cookie-banner button:first-of-type',
                '.gdpr-consent button:first-of-type'
            ];
            for (const sel of selectors) {
                try {
                    const btn = document.querySelector(sel);
                    if (btn && btn.offsetParent !== null) {
                        btn.click();
                        return;
                    }
                } catch (e) {}
            }
        })();
    """

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

        # Build JS code to run on each page
        js_code = []
        if self.config.dismiss_cookie_consent:
            js_code.append(self.COOKIE_CONSENT_JS)

        return CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            markdown_generator=md_generator,
            stream=True,  # Stream results as they complete
            excluded_tags=self.config.excluded_tags,
            word_count_threshold=self.config.word_count_threshold,
            exclude_external_links=self.config.exclude_external_links,
            js_code=js_code if js_code else None,
            delay_before_return_html=0.5 if js_code else 0,  # Wait for cookie banner to dismiss
            magic=self.config.enable_magic_mode,
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

        Uses persistent browser if called within context manager,
        otherwise creates a temporary browser session.

        Args:
            urls: List of URLs to crawl
            use_raw_markdown: If True, return raw_markdown; else fit_markdown

        Yields:
            CrawlOutput for each URL
        """
        if not urls:
            return

        run_config = self._build_run_config(use_raw_markdown)
        dispatcher = self._build_dispatcher()

        # Use persistent crawler if available (context manager pattern)
        if self._crawler:
            async for output in self._crawl_with_crawler(
                self._crawler, urls, run_config, dispatcher, use_raw_markdown
            ):
                yield output
        else:
            # Fallback: create temporary browser (less efficient)
            browser_config = self._build_browser_config()
            async with AsyncWebCrawler(config=browser_config) as crawler:
                async for output in self._crawl_with_crawler(
                    crawler, urls, run_config, dispatcher, use_raw_markdown
                ):
                    yield output

    async def _crawl_with_crawler(
        self,
        crawler: AsyncWebCrawler,
        urls: list[str],
        run_config: CrawlerRunConfig,
        dispatcher: MemoryAdaptiveDispatcher,
        use_raw_markdown: bool,
    ) -> AsyncIterator[CrawlOutput]:
        """Execute crawl with given crawler instance."""
        async for result in await crawler.arun_many(
            urls=urls,
            config=run_config,
            dispatcher=dispatcher,
        ):
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

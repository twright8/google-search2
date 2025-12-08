# Google Search + Crawl4AI Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a streaming async pipeline that searches Google, queues URLs, and extracts text via Crawl4AI.

**Architecture:** Queue-based producer/consumer pattern. Async Google Search feeds URLs into asyncio.Queue; Crawl4AI consumer batches and crawls with MemoryAdaptiveDispatcher; results stream out as pages complete.

**Tech Stack:** Python 3.11+, aiohttp, crawl4ai, pydantic-settings

---

## Task 1: Project Setup

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `src/__init__.py`

**Step 1: Create requirements.txt**

```txt
aiohttp>=3.9.0
crawl4ai>=0.4.0
pydantic-settings>=2.0.0
python-dotenv>=1.0.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
```

**Step 2: Create .env.example**

```env
# Google Search API
GOOGLE_API_KEY=your_api_key_here
GOOGLE_CX=your_cx_here
GOOGLE_REQUESTS_PER_MINUTE=100
GOOGLE_REQUESTS_PER_DAY=10000
GOOGLE_MAX_RESULTS_PER_QUERY=10

# Crawl4AI - Concurrency
CRAWLER_MAX_CONCURRENCY=10
CRAWLER_MEMORY_THRESHOLD_PERCENT=85

# Crawl4AI - Retry/Backoff
CRAWLER_RETRY_MAX=3
CRAWLER_RETRY_BASE_DELAY_MIN=1.0
CRAWLER_RETRY_BASE_DELAY_MAX=2.0
CRAWLER_RETRY_MAX_DELAY=30.0

# Crawl4AI - Content Processing
CRAWLER_USE_PRUNING_FILTER=true
CRAWLER_PRUNING_THRESHOLD=0.3
CRAWLER_HEADLESS=true

# Pipeline
PIPELINE_QUEUE_SIZE=100
PIPELINE_BATCH_SIZE=10
```

**Step 3: Create src/__init__.py**

```python
"""Google Search + Crawl4AI Pipeline."""
```

**Step 4: Create .env from example (copy your real credentials)**

```bash
cp .env.example .env
# Edit .env with your GOOGLE_API_KEY and GOOGLE_CX
```

**Step 5: Install dependencies**

Run: `pip install -r requirements.txt`

**Step 6: Install Crawl4AI browser**

Run: `crawl4ai-setup`

**Step 7: Commit**

```bash
git init
echo ".env" >> .gitignore
echo "__pycache__/" >> .gitignore
echo ".pytest_cache/" >> .gitignore
git add requirements.txt .env.example .gitignore src/__init__.py
git commit -m "chore: project setup with dependencies"
```

---

## Task 2: Configuration Module

**Files:**
- Create: `src/config.py`
- Test: `tests/test_config.py`

**Step 1: Create tests directory**

```bash
mkdir -p tests
touch tests/__init__.py
```

**Step 2: Write the failing test**

Create `tests/test_config.py`:

```python
import pytest
import os


def test_settings_loads_from_env(monkeypatch):
    """Settings should load values from environment variables."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test_key")
    monkeypatch.setenv("GOOGLE_CX", "test_cx")

    from src.config import Settings

    settings = Settings()
    assert settings.google_api_key == "test_key"
    assert settings.google_cx == "test_cx"


def test_settings_has_defaults(monkeypatch):
    """Settings should have sensible defaults for optional values."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test_key")
    monkeypatch.setenv("GOOGLE_CX", "test_cx")

    from src.config import Settings

    settings = Settings()
    assert settings.google_requests_per_minute == 100
    assert settings.crawler.max_concurrency == 10
    assert settings.crawler.use_pruning_filter is True


def test_crawler_config_from_env(monkeypatch):
    """CrawlerConfig should load from CRAWLER_ prefixed env vars."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test_key")
    monkeypatch.setenv("GOOGLE_CX", "test_cx")
    monkeypatch.setenv("CRAWLER_MAX_CONCURRENCY", "20")
    monkeypatch.setenv("CRAWLER_PRUNING_THRESHOLD", "0.5")

    from src.config import Settings

    settings = Settings()
    assert settings.crawler.max_concurrency == 20
    assert settings.crawler.pruning_threshold == 0.5
```

**Step 3: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.config'"

**Step 4: Write minimal implementation**

Create `src/config.py`:

```python
"""Configuration management via environment variables."""

from pydantic_settings import BaseSettings
from pydantic import Field


class CrawlerConfig(BaseSettings):
    """Crawl4AI configuration."""

    max_concurrency: int = 10
    memory_threshold_percent: float = 85.0
    retry_max: int = 3
    retry_base_delay_min: float = 1.0
    retry_base_delay_max: float = 2.0
    retry_max_delay: float = 30.0
    use_pruning_filter: bool = True
    pruning_threshold: float = 0.3
    headless: bool = True

    model_config = {"env_prefix": "CRAWLER_"}


class PipelineConfig(BaseSettings):
    """Pipeline configuration."""

    queue_size: int = 100
    batch_size: int = 10

    model_config = {"env_prefix": "PIPELINE_"}


class Settings(BaseSettings):
    """Main application settings."""

    # Google Search API
    google_api_key: str
    google_cx: str
    google_requests_per_minute: int = 100
    google_requests_per_day: int = 10000
    google_max_results_per_query: int = 10

    # Nested configs
    crawler: CrawlerConfig = Field(default_factory=CrawlerConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS (3 passed)

**Step 6: Commit**

```bash
git add src/config.py tests/test_config.py tests/__init__.py
git commit -m "feat: add configuration module with pydantic-settings"
```

---

## Task 3: Async Google Search Client

**Files:**
- Create: `src/google_search.py`
- Test: `tests/test_google_search.py`

**Step 1: Write the failing test**

Create `tests/test_google_search.py`:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_google_search.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.google_search'"

**Step 3: Write minimal implementation**

Create `src/google_search.py`:

```python
"""Async Google Custom Search API client."""

import asyncio
from typing import AsyncIterator

import aiohttp


class AsyncGoogleSearch:
    """Async client for Google Custom Search API."""

    BASE_URL = "https://www.googleapis.com/customsearch/v1"

    def __init__(
        self,
        api_key: str,
        cx: str,
        rate_limit_per_min: int = 100,
        max_results_per_query: int = 10,
    ):
        self.api_key = api_key
        self.cx = cx
        self.max_results_per_query = max_results_per_query
        self.semaphore = asyncio.Semaphore(rate_limit_per_min)

    async def search(self, query: str, num_results: int | None = None) -> list[dict]:
        """
        Execute a single search query.

        Args:
            query: Search query string
            num_results: Number of results (default: max_results_per_query)

        Returns:
            List of result items with 'title', 'link', 'snippet'
        """
        if num_results is None:
            num_results = self.max_results_per_query

        async with self.semaphore:
            async with aiohttp.ClientSession() as session:
                params = {
                    "key": self.api_key,
                    "cx": self.cx,
                    "q": query,
                    "num": min(num_results, 10),  # API max is 10
                }
                async with session.get(self.BASE_URL, params=params) as response:
                    response.raise_for_status()
                    data = await response.json()
                    return data.get("items", [])

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
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_google_search.py -v`
Expected: PASS (2 passed)

**Step 5: Commit**

```bash
git add src/google_search.py tests/test_google_search.py
git commit -m "feat: add async Google Search client"
```

---

## Task 4: Crawl4AI Wrapper

**Files:**
- Create: `src/crawler.py`
- Test: `tests/test_crawler.py`

**Step 1: Write the failing test**

Create `tests/test_crawler.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def test_crawler_config_builds_correctly():
    """ContentCrawler should build configs from CrawlerConfig."""
    from src.crawler import ContentCrawler
    from src.config import CrawlerConfig

    config = CrawlerConfig(
        max_concurrency=5,
        memory_threshold_percent=70.0,
        use_pruning_filter=True,
        pruning_threshold=0.4,
        headless=True,
    )

    crawler = ContentCrawler(config)

    browser_config = crawler._build_browser_config()
    assert browser_config.headless is True

    run_config = crawler._build_run_config()
    assert run_config.markdown_generator is not None


def test_crawler_dispatcher_has_rate_limiter():
    """Dispatcher should include RateLimiter with configured values."""
    from src.crawler import ContentCrawler
    from src.config import CrawlerConfig

    config = CrawlerConfig(
        retry_max=5,
        retry_base_delay_min=2.0,
        retry_base_delay_max=4.0,
        retry_max_delay=60.0,
    )

    crawler = ContentCrawler(config)
    dispatcher = crawler._build_dispatcher()

    assert dispatcher.rate_limiter is not None
    assert dispatcher.rate_limiter.max_retries == 5
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_crawler.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.crawler'"

**Step 3: Write minimal implementation**

Create `src/crawler.py`:

```python
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
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_crawler.py -v`
Expected: PASS (2 passed)

**Step 5: Commit**

```bash
git add src/crawler.py tests/test_crawler.py
git commit -m "feat: add Crawl4AI content crawler wrapper"
```

---

## Task 5: Queue-Based Pipeline

**Files:**
- Create: `src/pipeline.py`
- Test: `tests/test_pipeline.py`

**Step 1: Write the failing test**

Create `tests/test_pipeline.py`:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.pipeline'"

**Step 3: Write minimal implementation**

Create `src/pipeline.py`:

```python
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
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_pipeline.py -v`
Expected: PASS (2 passed)

**Step 5: Commit**

```bash
git add src/pipeline.py tests/test_pipeline.py
git commit -m "feat: add queue-based streaming pipeline"
```

---

## Task 6: Main Entry Point

**Files:**
- Modify: `main.py`

**Step 1: Update main.py**

Replace contents of `main.py`:

```python
"""Google Search + Crawl4AI Pipeline - Entry Point."""

import asyncio
import sys

from src.config import Settings
from src.google_search import AsyncGoogleSearch
from src.crawler import ContentCrawler
from src.pipeline import run_pipeline


async def main(queries: list[str] | None = None):
    """Run the pipeline with optional custom queries."""

    # Load configuration
    try:
        settings = Settings()
    except Exception as e:
        print(f"Configuration error: {e}")
        print("Ensure .env file exists with GOOGLE_API_KEY and GOOGLE_CX")
        sys.exit(1)

    # Default test queries
    if queries is None:
        queries = ["python web scraping tutorial", "async python best practices"]

    print(f"Running pipeline with {len(queries)} queries...")
    print(f"Crawler config: concurrency={settings.crawler.max_concurrency}, "
          f"pruning={settings.crawler.use_pruning_filter}")
    print("-" * 60)

    # Initialize clients
    google_client = AsyncGoogleSearch(
        api_key=settings.google_api_key,
        cx=settings.google_cx,
        rate_limit_per_min=settings.google_requests_per_minute,
        max_results_per_query=settings.google_max_results_per_query,
    )

    crawler = ContentCrawler(settings.crawler)

    # Run pipeline
    success_count = 0
    fail_count = 0

    async for result in run_pipeline(
        queries=queries,
        google_client=google_client,
        crawler=crawler,
        use_raw_markdown=not settings.crawler.use_pruning_filter,
        queue_size=settings.pipeline.queue_size,
        batch_size=settings.pipeline.batch_size,
    ):
        status = "OK" if result.success else "FAIL"
        content_len = len(result.content) if result.content else 0

        print(f"[{status}] {result.url[:70]}")
        if result.success:
            print(f"       {content_len:,} chars extracted")
            success_count += 1
        else:
            print(f"       Error: {result.error}")
            fail_count += 1

    print("-" * 60)
    print(f"Complete: {success_count} succeeded, {fail_count} failed")


if __name__ == "__main__":
    # Accept queries from command line
    queries = sys.argv[1:] if len(sys.argv) > 1 else None
    asyncio.run(main(queries))
```

**Step 2: Test manually**

Run: `python main.py "python tutorials"`
Expected: Pipeline runs, shows URLs being crawled with content lengths

**Step 3: Commit**

```bash
git add main.py
git commit -m "feat: add main entry point with CLI support"
```

---

## Task 7: Run All Tests

**Step 1: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests pass (7+ tests)

**Step 2: Run with coverage (optional)**

Run: `pip install pytest-cov && pytest tests/ --cov=src --cov-report=term-missing`

**Step 3: Final commit**

```bash
git add -A
git commit -m "chore: complete test pipeline implementation"
```

---

## Task 8: Integration Test (Manual)

**Step 1: Ensure .env has real credentials**

```bash
cat .env | grep -E "^GOOGLE_"
# Should show your API key and CX
```

**Step 2: Run with single query**

Run: `python main.py "python asyncio tutorial"`
Expected:
- Searches complete
- URLs crawled with content extracted
- Summary shows success/fail counts

**Step 3: Run with multiple queries**

Run: `python main.py "web scraping python" "crawl4ai usage"`
Expected: More URLs processed, streaming output

---

## Summary

| Task | Files | Tests |
|------|-------|-------|
| 1. Project Setup | requirements.txt, .env.example | - |
| 2. Config Module | src/config.py | 3 tests |
| 3. Google Search | src/google_search.py | 2 tests |
| 4. Crawler Wrapper | src/crawler.py | 2 tests |
| 5. Pipeline | src/pipeline.py | 2 tests |
| 6. Entry Point | main.py | manual |
| 7. Test Suite | - | all pass |
| 8. Integration | - | manual |

**Total:** 6 source files, 9+ automated tests, full TDD approach

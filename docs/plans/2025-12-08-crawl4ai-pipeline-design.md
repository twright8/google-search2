# Google Search + Crawl4AI Pipeline Design

**Date:** 2025-12-08
**Status:** Approved
**Purpose:** Test pipeline for Google Search → Crawl4AI text extraction

---

## Overview

A streaming async pipeline that:
1. Executes Google Custom Search API queries concurrently
2. Feeds URLs into an asyncio.Queue in real-time
3. Crawls URLs with Crawl4AI using MemoryAdaptiveDispatcher
4. Outputs filtered markdown text (with raw markdown fallback)

## Architecture

```
┌─────────────────┐     ┌─────────────┐     ┌─────────────────┐     ┌─────────────┐
│  Google Search  │────▶│  URL Queue  │────▶│   Crawl4AI      │────▶│   Results   │
│  (async/aiohttp)│     │  (asyncio)  │     │  (arun_many)    │     │   Stream    │
└─────────────────┘     └─────────────┘     └─────────────────┘     └─────────────┘
       Producer              Buffer              Consumer               Output
```

**Key Properties:**
- Search and crawl run concurrently (overlapping I/O)
- Backpressure via bounded queue (default 100)
- Results stream as pages complete

## Technology Choices

| Component | Choice | Rationale |
|-----------|--------|-----------|
| HTTP Client | `aiohttp` | Fastest async HTTP for Python |
| Web Crawler | Crawl4AI `AsyncWebCrawler` | LLM-optimized, async-first |
| Concurrency | `MemoryAdaptiveDispatcher` | Auto-scales based on system memory |
| Rate Limiting | Crawl4AI `RateLimiter` | Built-in exponential backoff |
| Content Filter | `PruningContentFilter` | Removes boilerplate heuristically |
| Config | `pydantic-settings` | Type-safe ENV loading |

## Configuration (ENV)

All parameters configurable via `.env`:

```env
# Google Search API
GOOGLE_API_KEY=your_key
GOOGLE_CX=your_cx
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

## Project Structure

```
google-search/
├── .env                    # Configuration (git-ignored)
├── .env.example            # Template with defaults
├── main.py                 # Entry point
├── requirements.txt        # Dependencies
├── src/
│   ├── __init__.py
│   ├── config.py           # Pydantic settings
│   ├── google_search.py    # Async Google Search client
│   ├── crawler.py          # Crawl4AI wrapper
│   └── pipeline.py         # Queue-based orchestration
└── docs/
    └── plans/
        └── 2025-12-08-crawl4ai-pipeline-design.md
```

## Component Details

### AsyncGoogleSearch

- Uses `aiohttp.ClientSession` for async HTTP
- Semaphore enforces rate limit (100 req/min)
- `search_many()` yields URLs as searches complete via `asyncio.as_completed()`

### ContentCrawler

- Wraps `AsyncWebCrawler` with configuration
- `BrowserConfig`: headless mode
- `CrawlerRunConfig`: cache bypass, markdown generator with optional pruning filter
- `MemoryAdaptiveDispatcher`: scales concurrency based on memory threshold
- `RateLimiter`: lightweight exponential backoff (configurable retries)

### Pipeline

- Producer: feeds URLs from Google Search into `url_queue`
- Consumer: batches URLs, calls `arun_many(stream=True)`, pushes to `results_queue`
- Main: yields `CrawlOutput` as results arrive
- Sentinel pattern (`None`) signals completion

## Output Format

```python
@dataclass
class CrawlOutput:
    url: str
    success: bool
    content: str | None  # fit_markdown or raw_markdown
    error: str | None
```

## Crawl4AI Summary

### Key Classes

| Class | Purpose |
|-------|---------|
| `AsyncWebCrawler` | Core async crawler, reuse single instance |
| `BrowserConfig` | Browser settings (headless, viewport) |
| `CrawlerRunConfig` | Per-crawl settings (cache, filters, selectors) |
| `arun()` | Single URL crawl |
| `arun_many()` | Batch/concurrent crawl with streaming |

### Dispatchers

| Dispatcher | Use Case |
|------------|----------|
| `SemaphoreDispatcher` | Fixed concurrency limit |
| `MemoryAdaptiveDispatcher` | Dynamic scaling based on memory |

### Content Output

| Property | Description |
|----------|-------------|
| `result.markdown.raw_markdown` | Full page content, markdown formatted |
| `result.markdown.fit_markdown` | Filtered content (requires PruningContentFilter) |
| `result.success` | Boolean - crawl succeeded |
| `result.error_message` | Error description if failed |

### PruningContentFilter

- Threshold: 0.0-1.0 (lower = more permissive)
- Removes navigation, ads, boilerplate heuristically
- Default threshold: 0.3 (configurable)

## Potential Optimizations

1. **Connection pooling**: Reuse `aiohttp.ClientSession` across searches
2. **Browser reuse**: Crawl4AI reuses browser via context manager
3. **Batch size tuning**: Adjust based on memory/network
4. **text_mode**: `BrowserConfig(text_mode=True)` for faster non-JS pages
5. **Caching**: Enable `CacheMode.ENABLED` for repeated URLs

## Alternative Configurations

### For JavaScript-heavy sites
```python
CrawlerRunConfig(
    wait_for="css:.content",  # Wait for element
    page_timeout=60000        # Longer timeout
)
```

### For simple static sites
```python
BrowserConfig(
    text_mode=True,  # Faster, no JS
    headless=True
)
```

### For high-volume crawling
```python
MemoryAdaptiveDispatcher(
    memory_threshold_percent=70,  # More conservative
    max_session_permit=20         # Higher concurrency
)
```

## Error Handling

- Google Search: `aiohttp` raises on HTTP errors
- Crawl4AI: Check `result.success`, access `result.error_message`
- Pipeline: Yields failed results with error info for downstream handling

## Dependencies

```
aiohttp>=3.9.0
crawl4ai>=0.4.0
pydantic-settings>=2.0.0
python-dotenv>=1.0.0
```

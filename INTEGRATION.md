# LLM Pipeline Integration Guide

Developer notes for integrating this search/crawl pipeline into an LLM-powered automation system.

## Architecture Overview

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌─────────────┐
│ LLM Agent   │────▶│ Google Search│────▶│ Crawl4AI    │────▶│ LLM Process │
│ (generates  │     │ (parallel    │     │ (streaming  │     │ (per-source │
│  queries)   │     │  queries)    │     │  results)   │     │  as ready)  │
└─────────────┘     └──────────────┘     └─────────────┘     └─────────────┘
```

## Key Configuration

### Reduce Results Per Query

Default is 10 results per query. For LLM processing, 5 is usually sufficient:

```bash
# .env
GOOGLE_MAX_RESULTS_PER_QUERY=5
```

Or pass directly:
```python
google_client = AsyncGoogleSearch(
    api_key=settings.google_api_key,
    cx=settings.google_cx,
    max_results_per_query=5,  # Reduce from default 10
    # ...
)
```

## Streaming Integration Pattern

The pipeline yields results as each page completes - **do not wait for all results**.

### Basic Pattern: Process Each Result Immediately

```python
import asyncio
from src.config import Settings
from src.google_search import AsyncGoogleSearch
from src.crawler import ContentCrawler
from src.pipeline import run_pipeline

async def process_with_llm(content: str, url: str) -> str:
    """Your LLM processing function."""
    # Call your LLM here (OpenAI, Anthropic, local, etc.)
    pass

async def search_and_process(queries: list[str]) -> list[dict]:
    settings = Settings()
    results = []

    async with AsyncGoogleSearch(
        api_key=settings.google_api_key,
        cx=settings.google_cx,
        max_results_per_query=5,  # Reduced for LLM use
        max_concurrent=settings.google_max_concurrent,
    ) as google_client, ContentCrawler(settings.crawler) as crawler:

        async for output in run_pipeline(
            queries=queries,
            google_client=google_client,
            crawler=crawler,
        ):
            if output.success:
                # Process immediately - don't wait for other results
                llm_result = await process_with_llm(output.content, output.url)
                results.append({
                    "url": output.url,
                    "content": output.content,
                    "llm_analysis": llm_result,
                })
            else:
                print(f"Failed: {output.url} - {output.error}")

    return results
```

### Advanced: Parallel LLM Processing with Semaphore

If your LLM supports concurrent requests, process in parallel while respecting rate limits:

```python
import asyncio

async def search_and_process_parallel(
    queries: list[str],
    llm_concurrency: int = 5,  # Max parallel LLM calls
) -> list[dict]:
    settings = Settings()
    results = []
    semaphore = asyncio.Semaphore(llm_concurrency)
    tasks = []

    async def process_one(output):
        async with semaphore:
            llm_result = await process_with_llm(output.content, output.url)
            return {
                "url": output.url,
                "content": output.content,
                "llm_analysis": llm_result,
            }

    async with AsyncGoogleSearch(...) as google_client, ContentCrawler(...) as crawler:
        async for output in run_pipeline(queries=queries, ...):
            if output.success:
                # Start LLM processing immediately, don't await
                task = asyncio.create_task(process_one(output))
                tasks.append(task)

        # Wait for all LLM processing to complete
        results = await asyncio.gather(*tasks)

    return results
```

### Streaming to Caller (Generator Pattern)

If your outer system also wants streaming:

```python
async def search_and_process_streaming(queries: list[str]):
    """Yields processed results as they complete."""
    async with AsyncGoogleSearch(...) as google_client, ContentCrawler(...) as crawler:
        async for output in run_pipeline(queries=queries, ...):
            if output.success:
                llm_result = await process_with_llm(output.content, output.url)
                yield {
                    "url": output.url,
                    "content": output.content,
                    "llm_analysis": llm_result,
                }

# Consumer
async for result in search_and_process_streaming(["my query"]):
    print(f"Got result: {result['url']}")
    # Process/store/forward immediately
```

## Performance Considerations

| Setting | Recommended | Notes |
|---------|-------------|-------|
| `GOOGLE_MAX_RESULTS_PER_QUERY` | 5 | Fewer results = faster, less LLM cost |
| `CRAWLER_MAX_CONCURRENCY` | 10-20 | Balance speed vs memory |
| `CRAWLER_BROWSER_TYPE` | `undetected` | Required for protected sites |
| `CRAWLER_ENABLE_MAGIC_MODE` | `false` | Enable only if seeing blocks |

## Content Size Management

LLMs have context limits. Consider truncating or summarizing:

```python
MAX_CONTENT_LENGTH = 50000  # ~12k tokens for GPT-4

async for output in run_pipeline(...):
    if output.success:
        content = output.content[:MAX_CONTENT_LENGTH]
        if len(output.content) > MAX_CONTENT_LENGTH:
            content += "\n\n[Content truncated...]"

        await process_with_llm(content, output.url)
```

## Error Handling

The pipeline handles crawl failures gracefully. Your integration should handle:

1. **Crawl failures** - `output.success == False`, check `output.error`
2. **Empty content** - Some pages may return minimal content
3. **LLM failures** - Wrap LLM calls in try/except
4. **Rate limits** - Both Google API and LLM provider limits

```python
async for output in run_pipeline(...):
    if not output.success:
        logger.warning(f"Crawl failed: {output.url} - {output.error}")
        continue

    if not output.content or len(output.content) < 100:
        logger.warning(f"Minimal content: {output.url}")
        continue

    try:
        result = await process_with_llm(output.content, output.url)
    except RateLimitError:
        await asyncio.sleep(60)
        result = await process_with_llm(output.content, output.url)
    except Exception as e:
        logger.error(f"LLM failed for {output.url}: {e}")
        continue
```

## Query Generation from LLM

If the LLM generates search queries dynamically:

```python
async def research_topic(topic: str) -> list[dict]:
    # Step 1: LLM generates search queries
    queries = await generate_queries_with_llm(topic)
    # e.g., ["python async best practices", "asyncio vs threading python"]

    # Step 2: Search and crawl
    async with ... as google_client, ... as crawler:
        sources = []
        async for output in run_pipeline(queries=queries, ...):
            if output.success:
                sources.append(output)

        # Step 3: LLM synthesizes all sources
        final_answer = await synthesize_with_llm(topic, sources)

    return final_answer
```

## API Costs Estimation

| Component | Cost Factor |
|-----------|-------------|
| Google Search API | $5 per 1000 queries (after free tier) |
| Crawl4AI | Free (local browser) |
| LLM Processing | Varies by provider and content length |

For 100 queries × 5 results = 500 pages crawled = 500 LLM calls.

## Quick Start Checklist

- [ ] Set `GOOGLE_MAX_RESULTS_PER_QUERY=5` in `.env`
- [ ] Use `async with` context managers for both clients
- [ ] Process results inside the `async for` loop (don't collect then process)
- [ ] Add content length limits before LLM calls
- [ ] Handle `output.success == False` cases
- [ ] Consider parallel LLM processing with semaphore

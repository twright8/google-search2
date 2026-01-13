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

    # Calculate daily limit (free tier = 100/day)
    daily_limit = 100 if settings.google_free_tier_only else settings.google_requests_per_day

    print(f"Running pipeline with {len(queries)} queries...")
    print(f"Google API: {'FREE TIER (100/day)' if settings.google_free_tier_only else f'{daily_limit}/day'}")
    print(f"Crawler: concurrency={settings.crawler.max_concurrency}, pruning={settings.crawler.use_pruning_filter}")
    print("-" * 60)

    # Run pipeline with context managers for optimal resource usage
    success_count = 0
    fail_count = 0

    async with AsyncGoogleSearch(
        api_key=settings.google_api_key,
        cx=settings.google_cx,
        rate_limit_per_min=settings.google_requests_per_minute,
        rate_limit_per_day=daily_limit,
        max_results_per_query=settings.google_max_results_per_query,
        max_concurrent=settings.google_max_concurrent,
        retry_max=settings.google_retry_max,
        retry_base_delay=settings.google_retry_base_delay,
        retry_max_delay=settings.google_retry_max_delay,
    ) as google_client, ContentCrawler(settings.crawler) as crawler:

        async for result in run_pipeline(
            queries=queries,
            google_client=google_client,
            crawler=crawler,
            use_raw_markdown=not settings.crawler.use_pruning_filter,
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
    asyncio.run(main(queries))

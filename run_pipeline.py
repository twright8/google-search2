"""Run pipeline and collect results for inspection in PyCharm console."""

import asyncio
from src.config import Settings
from src.google_search import AsyncGoogleSearch
from src.crawler import ContentCrawler
from src.pipeline import run_pipeline
import pandas as pd

async def search_and_crawl(queries: list[str]) -> list[dict]:
    """
    Run the pipeline and return results as a list of dicts.

    Args:
        queries: Search queries to execute

    Returns:
        List of results with url, success, content, error
    """
    settings = Settings()

    daily_limit = 100 if settings.google_free_tier_only else settings.google_requests_per_day

    results = []

    # Use context managers for optimal resource usage
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

        async for output in run_pipeline(
            queries=queries,
            google_client=google_client,
            crawler=crawler,
            use_raw_markdown=not settings.crawler.use_pruning_filter,
        ):
            results.append({
                "url": output.url,
                "success": output.success,
                "content": output.content,
                "error": output.error,
            })
            # Print progress
            status = "OK" if output.success else "FAIL"
            print(f"[{status}] {output.url[:60]}...")

    return results


# For PyCharm Python Console:
# 1. Right-click this file -> "Run File in Python Console"
# 2. Then run:
#
#    results = asyncio.run(search_and_crawl(["python async tutorial"]))
#
# 3. Inspect results:
#
#    len(results)
#    results[0]["url"]
#    results[0]["content"][:500]
#    [r["url"] for r in results if r["success"]]


if __name__ == "__main__":
    # Example usage
    test_queries = pd.read_csv("gsearches.csv")['query'].tolist()[0:5]
    results = asyncio.run(search_and_crawl(test_queries))

    print(f"\n{'='*60}")
    print(f"Collected {len(results)} results")
    print(f"Success: {sum(1 for r in results if r['success'])}")
    print(f"Failed: {sum(1 for r in results if not r['success'])}")

    # Results are now in `results` list for inspection

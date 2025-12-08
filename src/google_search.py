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

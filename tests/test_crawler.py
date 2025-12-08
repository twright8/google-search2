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

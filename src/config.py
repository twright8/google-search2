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

    # Anti-bot protection
    browser_type: str = "chromium"  # "chromium" or "undetected"
    enable_stealth: bool = True  # Use playwright-stealth patches
    dismiss_cookie_consent: bool = True  # Auto-click cookie consent buttons
    enable_magic_mode: bool = False  # Extra anti-bot simulation (adds some overhead)

    # Content filtering
    excluded_tags: list[str] = ["nav", "footer", "header", "aside", "advertisement"]
    word_count_threshold: int = 20
    exclude_external_links: bool = True

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
    google_max_concurrent: int = 50  # Max parallel Google API requests
    google_free_tier_only: bool = False  # When True, limits to 100 req/day (free tier)

    # Google Search retry settings
    google_retry_max: int = 3
    google_retry_base_delay: float = 1.0
    google_retry_max_delay: float = 30.0

    # Nested configs
    crawler: CrawlerConfig = Field(default_factory=CrawlerConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

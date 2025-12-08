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

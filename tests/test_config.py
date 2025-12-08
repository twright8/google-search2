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

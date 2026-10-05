"""Тесты загрузки конфигурации поиска и настроек приложения."""

from pathlib import Path
from clinic_scraper.config import load_search_config, get_settings


def test_load_search_config():
    config_path = Path("config") / "search_config.json"
    assert config_path.exists(), "Файл config/search_config.json должен существовать"

    cfg = load_search_config(config_path)
    assert cfg.city_default == "Хабаровск"
    assert len(cfg.search_queries) >= 10
    assert "косметология" in cfg.search_queries
    assert "гбуз" in cfg.stop_words_gov
    assert "Cortexil" in cfg.prp_brands
    assert len(cfg.regex_filter.injection_keywords) > 0
    assert "{site_text}" in cfg.gemini.prompt_template


def test_get_settings():
    settings = get_settings(city="Хабаровск")
    assert settings.city == "Хабаровск"
    assert settings.crawler.concurrency >= 1
    assert settings.harvesters.dgis.page_size >= 1
    assert settings.gemini.rpm >= 1
    assert settings.pipeline.checkpoint_interval >= 1
    assert settings.search_config is not None


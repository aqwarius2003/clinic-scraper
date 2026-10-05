"""Конфигурация приложения ClinicScraper.
Объединяет параметры окружения (.env) и бизнес-правила (search_config.json).
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


class RegexFilterConfig(BaseModel):
    injection_keywords: List[str] = Field(default_factory=list)
    prp_keywords: List[str] = Field(default_factory=list)


class GeminiPromptConfig(BaseModel):
    prompt_template: str
    rules: Dict[str, Any] = Field(default_factory=dict)


class SearchConfig(BaseModel):
    city_default: str = "Хабаровск"
    search_queries: List[str] = Field(default_factory=list)
    stop_words_gov: List[str] = Field(default_factory=list)
    prp_brands: Dict[str, List[str]] = Field(default_factory=dict)
    regex_filter: RegexFilterConfig = Field(default_factory=RegexFilterConfig)
    gemini: GeminiPromptConfig


class AppSettings(BaseModel):
    """Основные системные настройки приложения."""
    city: str = "Хабаровск"
    gemini_api_keys: List[str] = Field(default_factory=list)
    public_keys_2gis: List[str] = Field(default_factory=lambda: ["ruzhub8994", "rurbbn3446", "ruregt3044"])
    use_2gis: bool = True
    use_yandex: bool = True
    crawler_concurrency: int = 8
    crawler_timeout: int = 15
    crawler_max_pages: int = 4
    use_playwright_fallback: bool = True
    gemini_model: str = "gemini-3.1-flash-lite"
    gemini_temperature: float = 0.1
    gemini_rpm: int = 14
    gemini_tpm: int = 250000
    gemini_concurrency: int = 4
    max_pages_2gis: int = 5
    max_results_yandex_per_query: int = 70
    data_dir: Path = Field(default_factory=lambda: Path("data"))
    output_dir: Path = Field(default_factory=lambda: Path("output"))
    cache_dir: Path = Field(default_factory=lambda: Path("cache"))
    search_config: SearchConfig


def load_search_config(config_path: Optional[Path] = None) -> SearchConfig:
    """Загружает JSON с поисковыми словами, правилами отсечения и промптами."""
    if config_path is None:
        config_path = Path("config") / "search_config.json"
    if not config_path.exists():
        raise FileNotFoundError(f"Файл конфигурации поиска не найден: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return SearchConfig(**data)


def get_settings(
    city: Optional[str] = None,
    config_path: Optional[Path] = None
) -> AppSettings:
    """Инициализирует и возвращает экземпляр AppSettings из .env и search_config.json."""
    search_cfg = load_search_config(config_path)

    # Определение города (параметр CLI > ENV > дефолт из JSON)
    selected_city = (
        city
        or os.getenv("CITY")
        or search_cfg.city_default
    ).strip()

    # Gemini API keys
    raw_keys = os.getenv("GEMINI_API_KEYS", "") or os.getenv("GEMINI_API_KEY", "")
    gemini_keys = [
        k.strip() for k in raw_keys.split(",")
        if k.strip() and not k.strip().startswith("ВСТАВЬ")
    ]

    # 2GIS Public Keys
    raw_2gis = os.getenv("PUBLIC_KEYS_2GIS", "")
    if raw_2gis:
        keys_2gis = [k.strip() for k in raw_2gis.split(",") if k.strip()]
    else:
        keys_2gis = ["ruzhub8994", "rurbbn3446", "ruregt3044"]

    data_d = Path("data")
    data_d.mkdir(exist_ok=True)
    out_d = Path("output")
    out_d.mkdir(exist_ok=True)
    cache_d = Path("cache")
    cache_d.mkdir(exist_ok=True)

    return AppSettings(
        city=selected_city,
        gemini_api_keys=gemini_keys,
        public_keys_2gis=keys_2gis,
        use_2gis=os.getenv("USE_2GIS", "true").lower() in ("true", "1", "yes"),
        use_yandex=os.getenv("USE_YANDEX", "true").lower() in ("true", "1", "yes"),
        crawler_concurrency=int(os.getenv("CRAWLER_CONCURRENCY", "8")),
        crawler_timeout=int(os.getenv("CRAWLER_TIMEOUT", "15")),
        crawler_max_pages=int(os.getenv("CRAWLER_MAX_PAGES", "4")),
        use_playwright_fallback=os.getenv("USE_PLAYWRIGHT_FALLBACK", "true").lower() in ("true", "1", "yes"),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite"),
        gemini_temperature=float(os.getenv("GEMINI_TEMPERATURE", "0.1")),
        gemini_rpm=int(os.getenv("GEMINI_RPM", "14")),
        gemini_tpm=int(os.getenv("GEMINI_TPM", "250000")),
        gemini_concurrency=int(os.getenv("GEMINI_CONCURRENCY", "4")),
        max_pages_2gis=int(os.getenv("MAX_PAGES_2GIS", "5")),
        max_results_yandex_per_query=int(os.getenv("MAX_RESULTS_YANDEX", "70")),
        data_dir=data_d,
        output_dir=out_d,
        cache_dir=cache_d,
        search_config=search_cfg,
    )

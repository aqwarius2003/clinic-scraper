"""Конфигурация приложения ClinicScraper.
Разделение ответственности:
- search_config.json: строго предметная область (что ищем, как квалифицируем, с каким промптом)
- AppSettings / .env: инфраструктура, секреты, квоты, потоки и тайм-ауты
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


# ==============================================================================
# 1. МОДЕЛИ ПРЕДМЕТНОЙ КОНФИГУРАЦИИ (search_config.json)
# ==============================================================================

class RegexFilterConfig(BaseModel):
    injection_keywords: List[str] = Field(default_factory=list)
    prp_keywords: List[str] = Field(default_factory=list)


class DedupRulesConfig(BaseModel):
    social_domains: List[str] = Field(default_factory=lambda: ["vk.com", "taplink.cc", "t.me"])
    aggregator_domains: List[str] = Field(
        default_factory=lambda: ["2gis", "yandex", "zoon", "prodoctorov", "doctu", "yell"]
    )
    brand_stop_words: List[str] = Field(default_factory=list)
    street_stop_words: List[str] = Field(default_factory=list)


class CrawlerSearchConfig(BaseModel):
    max_pages_per_site: int = 4
    max_text_chars: int = 35000
    max_emails: int = 3
    target_link_patterns: List[str] = Field(
        default_factory=lambda: [
            r"(price|prays|uslug|service|tsen|cost|цен|прайс|услуг)",
            r"(vrach|doctor|specialist|team|kollektiv|врач|специалист|команда|о-нас)",
            r"(contact|kontakty|контакт)"
        ]
    )


class DGisSearchConfig(BaseModel):
    page_size: int = 50
    max_pages: int = 5


class YandexSearchConfig(BaseModel):
    max_results_per_query: int = 70
    scroll_count: int = 7


class HarvestersSearchConfig(BaseModel):
    dgis: DGisSearchConfig = Field(default_factory=DGisSearchConfig)
    yandex: YandexSearchConfig = Field(default_factory=YandexSearchConfig)


class GeminiSearchConfig(BaseModel):
    prompt_template: str


class SearchConfig(BaseModel):
    """Творческая предметная конфигурация: что ищем, чем фильтруем и с каким промптом."""
    city: str = "Хабаровск"
    search_queries: List[str] = Field(default_factory=list)
    stop_words_gov: List[str] = Field(default_factory=list)
    prp_brands: Dict[str, List[str]] = Field(default_factory=dict)
    regex_filter: RegexFilterConfig = Field(default_factory=RegexFilterConfig)
    dedup_rules: DedupRulesConfig = Field(default_factory=DedupRulesConfig)
    crawler: CrawlerSearchConfig = Field(default_factory=CrawlerSearchConfig)
    harvesters: HarvestersSearchConfig = Field(default_factory=HarvestersSearchConfig)
    gemini: GeminiSearchConfig


# ==============================================================================
# 2. СИСТЕМНЫЕ И ИНФРАСТРУКТУРНЫЕ НАСТРОЙКИ (AppSettings / .env)
# ==============================================================================

class AppSettings(BaseModel):
    """Инфраструктурные и системные параметры приложения."""
    city: str

    # Секреты и ключи
    gemini_api_keys: List[str] = Field(default_factory=list)
    public_keys_2gis: List[str] = Field(default_factory=list)

    # Флаги источников
    use_2gis: bool = True
    use_yandex: bool = True
    use_playwright_fallback: bool = True

    # Инфраструктура краулера
    crawler_concurrency: int = 8
    crawler_timeout: int = 15
    playwright_timeout_ms: int = 20000
    playwright_wait_ms: int = 2500

    # Сетевые параметры 2GIS
    dgis_request_delay: float = 0.35
    dgis_timeout: int = 15
    dgis_base_url: str = "https://catalog.api.2gis.com/3.0/items"

    # Сетевые параметры Яндекс
    yandex_scroll_delta: int = 2200
    yandex_scroll_wait_ms: int = 1100
    yandex_load_timeout_ms: int = 35000
    yandex_initial_wait_ms: int = 3500
    yandex_viewport_width: int = 1400
    yandex_viewport_height: int = 900

    # Технические квоты и параметры Gemini
    gemini_model: str = "gemini-3.1-flash-lite"
    gemini_temperature: float = 0.1
    gemini_rpm: int = 14
    gemini_tpm: int = 250000
    gemini_concurrency: int = 4
    gemini_max_retries: int = 3
    gemini_backoff_seconds: float = 5.0
    gemini_max_prompt_chars: int = 28000

    # Пайплайн и пути
    checkpoint_interval: int = 15
    data_dir: Path
    output_dir: Path
    cache_dir: Path

    # Ссылка на предметную конфигурацию
    search_config: SearchConfig


def load_search_config(config_path: Optional[Path] = None) -> SearchConfig:
    """Загружает JSON с предметными поисковыми словами и правилами."""
    if config_path is None:
        config_path = Path("config") / "search_config.json"
    if not config_path.exists():
        raise FileNotFoundError(f"Файл конфигурации не найден: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return SearchConfig(**data)


def get_settings(
    city: Optional[str] = None,
    config_path: Optional[Path] = None
) -> AppSettings:
    """Инициализирует системные AppSettings (.env + defaults) и загружает search_config.json."""
    search_cfg = load_search_config(config_path)

    # Город: CLI > ENV > search_config.json
    selected_city = (
        city
        or os.getenv("CITY")
        or search_cfg.city
    ).strip()

    # Секреты Gemini
    raw_keys = os.getenv("GEMINI_API_KEYS", "") or os.getenv("GEMINI_API_KEY", "")
    gemini_keys = [
        k.strip() for k in raw_keys.split(",")
        if k.strip() and not k.strip().startswith("ВСТАВЬ")
    ]

    # Секреты 2GIS
    raw_2gis = os.getenv("PUBLIC_KEYS_2GIS", "")
    if raw_2gis:
        keys_2gis = [k.strip() for k in raw_2gis.split(",") if k.strip()]
    else:
        keys_2gis = ["ruzhub8994", "rurbbn3446", "ruregt3044"]

    data_dir_path = Path(os.getenv("DATA_DIR", "data"))
    data_dir_path.mkdir(parents=True, exist_ok=True)

    output_dir_path = Path(os.getenv("OUTPUT_DIR", "output"))
    output_dir_path.mkdir(parents=True, exist_ok=True)

    cache_dir_path = Path(os.getenv("CACHE_DIR", "cache"))
    cache_dir_path.mkdir(parents=True, exist_ok=True)

    return AppSettings(
        city=selected_city,
        gemini_api_keys=gemini_keys,
        public_keys_2gis=keys_2gis,
        use_2gis=os.getenv("USE_2GIS", "true").lower() in ("true", "1", "yes"),
        use_yandex=os.getenv("USE_YANDEX", "true").lower() in ("true", "1", "yes"),
        use_playwright_fallback=os.getenv("USE_PLAYWRIGHT_FALLBACK", "true").lower() in ("true", "1", "yes"),
        crawler_concurrency=int(os.getenv("CRAWLER_CONCURRENCY", "8")),
        crawler_timeout=int(os.getenv("CRAWLER_TIMEOUT", "15")),
        playwright_timeout_ms=int(os.getenv("PLAYWRIGHT_TIMEOUT_MS", "20000")),
        playwright_wait_ms=int(os.getenv("PLAYWRIGHT_WAIT_MS", "2500")),
        dgis_request_delay=float(os.getenv("DGIS_REQUEST_DELAY", "0.35")),
        dgis_timeout=int(os.getenv("DGIS_TIMEOUT", "15")),
        dgis_base_url=os.getenv("DGIS_BASE_URL", "https://catalog.api.2gis.com/3.0/items"),
        yandex_scroll_delta=int(os.getenv("YANDEX_SCROLL_DELTA", "2200")),
        yandex_scroll_wait_ms=int(os.getenv("YANDEX_SCROLL_WAIT_MS", "1100")),
        yandex_load_timeout_ms=int(os.getenv("YANDEX_LOAD_TIMEOUT_MS", "35000")),
        yandex_initial_wait_ms=int(os.getenv("YANDEX_INITIAL_WAIT_MS", "3500")),
        yandex_viewport_width=int(os.getenv("YANDEX_VIEWPORT_WIDTH", "1400")),
        yandex_viewport_height=int(os.getenv("YANDEX_VIEWPORT_HEIGHT", "900")),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite"),
        gemini_temperature=float(os.getenv("GEMINI_TEMPERATURE", "0.1")),
        gemini_rpm=int(os.getenv("GEMINI_RPM", "14")),
        gemini_tpm=int(os.getenv("GEMINI_TPM", "250000")),
        gemini_concurrency=int(os.getenv("GEMINI_CONCURRENCY", "4")),
        gemini_max_retries=int(os.getenv("GEMINI_MAX_RETRIES", "3")),
        gemini_backoff_seconds=float(os.getenv("GEMINI_BACKOFF_SECONDS", "5.0")),
        gemini_max_prompt_chars=int(os.getenv("GEMINI_MAX_PROMPT_CHARS", "28000")),
        checkpoint_interval=int(os.getenv("CHECKPOINT_INTERVAL", "15")),
        data_dir=data_dir_path,
        output_dir=output_dir_path,
        cache_dir=cache_dir_path,
        search_config=search_cfg,
    )

"""Конфигурация приложения ClinicScraper.
Объединяет параметры окружения (.env) и бизнес-правила (search_config.json).
Все параметры вынесены из кода и могут переопределяться через .env или JSON-конфиг.
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


class DedupRulesConfig(BaseModel):
    social_domains: List[str] = Field(default_factory=lambda: ["vk.com", "taplink.cc", "t.me"])
    aggregator_domains: List[str] = Field(
        default_factory=lambda: ["2gis", "yandex", "zoon", "prodoctorov", "doctu", "yell"]
    )
    brand_stop_words: List[str] = Field(default_factory=list)
    street_stop_words: List[str] = Field(default_factory=list)


class CrawlerConfig(BaseModel):
    concurrency: int = 8
    timeout: int = 15
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
    playwright_timeout_ms: int = 20000
    playwright_wait_ms: int = 2500


class DGisConfig(BaseModel):
    base_url: str = "https://catalog.api.2gis.com/3.0/items"
    page_size: int = 50
    max_pages: int = 5
    request_delay_seconds: float = 0.35
    timeout_seconds: int = 15


class YandexConfig(BaseModel):
    max_results_per_query: int = 70
    scroll_count: int = 7
    scroll_delta: int = 2200
    scroll_wait_ms: int = 1100
    load_timeout_ms: int = 35000
    initial_wait_ms: int = 3500
    viewport_width: int = 1400
    viewport_height: int = 900


class HarvestersConfig(BaseModel):
    dgis: DGisConfig = Field(default_factory=DGisConfig)
    yandex: YandexConfig = Field(default_factory=YandexConfig)


class GeminiConfig(BaseModel):
    model: str = "gemini-3.1-flash-lite"
    temperature: float = 0.1
    rpm: int = 14
    tpm: int = 250000
    concurrency: int = 4
    max_retries: int = 3
    backoff_seconds: float = 5.0
    max_prompt_chars: int = 28000
    prompt_template: str


class PipelineConfig(BaseModel):
    checkpoint_interval: int = 15
    data_dir: str = "data"
    output_dir: str = "output"
    cache_dir: str = "cache"


class SearchConfig(BaseModel):
    city: str = "Хабаровск"
    search_queries: List[str] = Field(default_factory=list)
    stop_words_gov: List[str] = Field(default_factory=list)
    prp_brands: Dict[str, List[str]] = Field(default_factory=dict)
    regex_filter: RegexFilterConfig = Field(default_factory=RegexFilterConfig)
    dedup_rules: DedupRulesConfig = Field(default_factory=DedupRulesConfig)
    crawler: CrawlerConfig = Field(default_factory=CrawlerConfig)
    harvesters: HarvestersConfig = Field(default_factory=HarvestersConfig)
    gemini: GeminiConfig
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)


class AppSettings(BaseModel):
    """Итоговые настройки приложения, объединяющие CLI, .env и search_config.json."""
    city: str
    gemini_api_keys: List[str] = Field(default_factory=list)
    public_keys_2gis: List[str] = Field(default_factory=list)
    use_2gis: bool = True
    use_yandex: bool = True
    use_playwright_fallback: bool = True
    crawler: CrawlerConfig
    harvesters: HarvestersConfig
    gemini: GeminiConfig
    pipeline: PipelineConfig
    data_dir: Path
    output_dir: Path
    cache_dir: Path
    search_config: SearchConfig


def load_search_config(config_path: Optional[Path] = None) -> SearchConfig:
    """Загружает JSON с поисковыми словами, правилами отсечения и промптами."""
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
    """Инициализирует и возвращает экземпляр AppSettings с иерархией: CLI > .env > search_config.json."""
    search_cfg = load_search_config(config_path)

    # 1. Город: CLI флаг > ENV > search_config.json
    selected_city = (
        city
        or os.getenv("CITY")
        or search_cfg.city
    ).strip()

    # 2. Ключи Gemini: ENV > пусто
    raw_keys = os.getenv("GEMINI_API_KEYS", "") or os.getenv("GEMINI_API_KEY", "")
    gemini_keys = [
        k.strip() for k in raw_keys.split(",")
        if k.strip() and not k.strip().startswith("ВСТАВЬ")
    ]

    # 3. Ключи 2GIS: ENV > дефолт
    raw_2gis = os.getenv("PUBLIC_KEYS_2GIS", "")
    if raw_2gis:
        keys_2gis = [k.strip() for k in raw_2gis.split(",") if k.strip()]
    else:
        keys_2gis = ["ruzhub8994", "rurbbn3446", "ruregt3044"]

    # 4. Конфигурация Crawler с поддержкой ENV
    crawler_cfg = search_cfg.crawler.model_copy()
    if os.getenv("CRAWLER_CONCURRENCY"):
        crawler_cfg.concurrency = int(os.environ["CRAWLER_CONCURRENCY"])
    if os.getenv("CRAWLER_TIMEOUT"):
        crawler_cfg.timeout = int(os.environ["CRAWLER_TIMEOUT"])
    if os.getenv("CRAWLER_MAX_PAGES"):
        crawler_cfg.max_pages_per_site = int(os.environ["CRAWLER_MAX_PAGES"])
    if os.getenv("CRAWLER_MAX_TEXT_CHARS"):
        crawler_cfg.max_text_chars = int(os.environ["CRAWLER_MAX_TEXT_CHARS"])
    if os.getenv("CRAWLER_MAX_EMAILS"):
        crawler_cfg.max_emails = int(os.environ["CRAWLER_MAX_EMAILS"])
    if os.getenv("PLAYWRIGHT_TIMEOUT_MS"):
        crawler_cfg.playwright_timeout_ms = int(os.environ["PLAYWRIGHT_TIMEOUT_MS"])
    if os.getenv("PLAYWRIGHT_WAIT_MS"):
        crawler_cfg.playwright_wait_ms = int(os.environ["PLAYWRIGHT_WAIT_MS"])

    # 5. Конфигурация Harvesters с поддержкой ENV
    harvesters_cfg = search_cfg.harvesters.model_copy()
    if os.getenv("MAX_PAGES_2GIS"):
        harvesters_cfg.dgis.max_pages = int(os.environ["MAX_PAGES_2GIS"])
    if os.getenv("DGIS_REQUEST_DELAY"):
        harvesters_cfg.dgis.request_delay_seconds = float(os.environ["DGIS_REQUEST_DELAY"])
    if os.getenv("DGIS_TIMEOUT"):
        harvesters_cfg.dgis.timeout_seconds = int(os.environ["DGIS_TIMEOUT"])
    if os.getenv("DGIS_PAGE_SIZE"):
        harvesters_cfg.dgis.page_size = int(os.environ["DGIS_PAGE_SIZE"])

    if os.getenv("MAX_RESULTS_YANDEX"):
        harvesters_cfg.yandex.max_results_per_query = int(os.environ["MAX_RESULTS_YANDEX"])
    if os.getenv("YANDEX_SCROLL_COUNT"):
        harvesters_cfg.yandex.scroll_count = int(os.environ["YANDEX_SCROLL_COUNT"])
    if os.getenv("YANDEX_LOAD_TIMEOUT_MS"):
        harvesters_cfg.yandex.load_timeout_ms = int(os.environ["YANDEX_LOAD_TIMEOUT_MS"])

    # 6. Конфигурация Gemini с поддержкой ENV
    gemini_cfg = search_cfg.gemini.model_copy()
    if os.getenv("GEMINI_MODEL"):
        gemini_cfg.model = os.environ["GEMINI_MODEL"]
    if os.getenv("GEMINI_TEMPERATURE"):
        gemini_cfg.temperature = float(os.environ["GEMINI_TEMPERATURE"])
    if os.getenv("GEMINI_RPM"):
        gemini_cfg.rpm = int(os.environ["GEMINI_RPM"])
    if os.getenv("GEMINI_TPM"):
        gemini_cfg.tpm = int(os.environ["GEMINI_TPM"])
    if os.getenv("GEMINI_CONCURRENCY"):
        gemini_cfg.concurrency = int(os.environ["GEMINI_CONCURRENCY"])
    if os.getenv("GEMINI_MAX_RETRIES"):
        gemini_cfg.max_retries = int(os.environ["GEMINI_MAX_RETRIES"])
    if os.getenv("GEMINI_BACKOFF_SECONDS"):
        gemini_cfg.backoff_seconds = float(os.environ["GEMINI_BACKOFF_SECONDS"])
    if os.getenv("GEMINI_MAX_PROMPT_CHARS"):
        gemini_cfg.max_prompt_chars = int(os.environ["GEMINI_MAX_PROMPT_CHARS"])

    # 7. Конфигурация пайплайна и путей
    pipeline_cfg = search_cfg.pipeline.model_copy()
    if os.getenv("CHECKPOINT_INTERVAL"):
        pipeline_cfg.checkpoint_interval = int(os.environ["CHECKPOINT_INTERVAL"])

    data_dir_path = Path(os.getenv("DATA_DIR", pipeline_cfg.data_dir))
    data_dir_path.mkdir(parents=True, exist_ok=True)

    output_dir_path = Path(os.getenv("OUTPUT_DIR", pipeline_cfg.output_dir))
    output_dir_path.mkdir(parents=True, exist_ok=True)

    cache_dir_path = Path(os.getenv("CACHE_DIR", pipeline_cfg.cache_dir))
    cache_dir_path.mkdir(parents=True, exist_ok=True)

    return AppSettings(
        city=selected_city,
        gemini_api_keys=gemini_keys,
        public_keys_2gis=keys_2gis,
        use_2gis=os.getenv("USE_2GIS", "true").lower() in ("true", "1", "yes"),
        use_yandex=os.getenv("USE_YANDEX", "true").lower() in ("true", "1", "yes"),
        use_playwright_fallback=os.getenv("USE_PLAYWRIGHT_FALLBACK", "true").lower() in ("true", "1", "yes"),
        crawler=crawler_cfg,
        harvesters=harvesters_cfg,
        gemini=gemini_cfg,
        pipeline=pipeline_cfg,
        data_dir=data_dir_path,
        output_dir=output_dir_path,
        cache_dir=cache_dir_path,
        search_config=search_cfg,
    )

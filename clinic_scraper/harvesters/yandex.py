"""Сборщик организаций из Яндекс.Карт с использованием Playwright."""

from typing import List, Set
from urllib.parse import quote

from clinic_scraper.config import AppSettings
from clinic_scraper.core.logger import logger
from clinic_scraper.core.punycode import REALISTIC_HEADERS
from clinic_scraper.harvesters.base import BaseHarvester
from clinic_scraper.models import RawClinic


class YandexHarvester(BaseHarvester):
    """Сборщик данных Яндекс.Карт с эмуляцией пользовательского скролла."""

    def __init__(self, settings: AppSettings):
        self.settings = settings
        self.yandex_search_cfg = settings.search_config.harvesters.yandex
        self.city = settings.city
        self.queries = settings.search_config.search_queries
        self.stop_words = [sw.lower() for sw in settings.search_config.stop_words_gov]
        self.max_results = self.yandex_search_cfg.max_results_per_query
        self.scroll_count = self.yandex_search_cfg.scroll_count
        self.scroll_delta = settings.yandex_scroll_delta
        self.scroll_wait_ms = settings.yandex_scroll_wait_ms
        self.load_timeout_ms = settings.yandex_load_timeout_ms
        self.initial_wait_ms = settings.yandex_initial_wait_ms
        self.viewport = {
            "width": settings.yandex_viewport_width,
            "height": settings.yandex_viewport_height,
        }

    async def harvest(self) -> List[RawClinic]:
        if not self.settings.use_yandex:
            logger.info("Яндекс сбор отключен настройкой USE_YANDEX=false")
            return []

        logger.info(f"→ Яндекс.Карты (Playwright) сбор для города: {self.city}...")
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("Пакет Playwright не установлен. Установите: poetry run playwright install chromium")
            return []

        clinics: List[RawClinic] = []
        seen: Set[str] = set()

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"]
            )
            context = await browser.new_context(
                user_agent=REALISTIC_HEADERS["User-Agent"],
                viewport=self.viewport
            )
            page = await context.new_page()

            for query in self.queries:
                full_search = f"{query} {self.city}"
                url = f"https://yandex.ru/maps/?text={quote(full_search)}"
                logger.info(f"Яндекс поиск: {full_search}")
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=self.load_timeout_ms)
                    await page.wait_for_timeout(self.initial_wait_ms)

                    # Скролл списка результатов для дозагрузки карточек
                    for _ in range(self.scroll_count):
                        await page.mouse.wheel(0, self.scroll_delta)
                        await page.wait_for_timeout(self.scroll_wait_ms)

                    cards = await page.query_selector_all(
                        "div[class*='search-snippet-view'], div[class*='business-snippet'], div[class*='snippet']"
                    )
                    for card in cards[:self.max_results]:
                        try:
                            name_el = await card.query_selector("div[class*='title'] a, a[class*='title'], div[class*='title']")
                            name = (await name_el.inner_text()).strip() if name_el else ""
                            if not name or name.lower() in seen:
                                continue
                            if any(sw in name.lower() for sw in self.stop_words):
                                continue

                            phone = ""
                            phone_el = await card.query_selector("span[class*='phone'], a[href^='tel:']")
                            if phone_el:
                                phone = (await phone_el.inner_text()).strip()

                            site = ""
                            for a in await card.query_selector_all("a[href^='http']"):
                                href = await a.get_attribute("href") or ""
                                if "yandex" not in href and "maps" not in href:
                                    site = href
                                    break

                            addr_el = await card.query_selector("div[class*='address'], span[class*='address']")
                            address = (await addr_el.inner_text()).strip() if addr_el else ""

                            badge_el = await card.query_selector("div[class*='badge'], div[class*='features'], div[class*='rubric']")
                            snippet = (await badge_el.inner_text()).strip() if badge_el else ""

                            clinics.append(RawClinic(
                                source_id=f"ya_{abs(hash(name + phone))}",
                                name=name,
                                address=address,
                                phones=[phone] if phone else [],
                                site=site,
                                rubrics=[query],
                                source="yandex",
                                snippet=snippet
                            ))
                            seen.add(name.lower())
                        except Exception:
                            continue
                except Exception as e:
                    logger.warning(f"Яндекс ошибка поиска '{query}': {e}")

            await browser.close()

        logger.info(f"Яндекс успешно собрал: {len(clinics)} организаций")
        return clinics

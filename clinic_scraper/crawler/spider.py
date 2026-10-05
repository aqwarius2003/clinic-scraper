"""Умный асинхронный краулер медицинских сайтов (SmartCrawler)."""

import asyncio
import re
from typing import List, Dict, Any, Set
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from diskcache import Cache
import httpx

from clinic_scraper.config import AppSettings
from clinic_scraper.core.logger import logger
from clinic_scraper.crawler.http_fetcher import HttpFetcher
from clinic_scraper.crawler.pw_fetcher import PlaywrightFetcher
from clinic_scraper.models import RawClinic


class SmartCrawler:
    """Асинхронный паук для обхода сайтов организаций и извлечения контента."""

    def __init__(self, settings: AppSettings):
        self.settings = settings
        self.cache = Cache(str(settings.cache_dir))
        self.http_fetcher = HttpFetcher(self.cache, timeout=settings.crawler_timeout)
        self.pw_fetcher = PlaywrightFetcher(self.cache)
        self.concurrency = settings.crawler_concurrency
        self.max_pages = settings.crawler_max_pages
        self.use_pw_fallback = settings.use_playwright_fallback

    def extract_links(self, html: str, base_url: str) -> List[str]:
        """Находит ссылки на ключевые разделы: прайсы, врачи/специалисты, контакты."""
        soup = BeautifulSoup(html, "lxml")
        patterns = [
            r"(price|prays|uslug|service|tsen|cost|цен|прайс|услуг)",
            r"(vrach|doctor|specialist|team|kollektiv|врач|специалист|команда|о-нас)",
            r"(contact|kontakty|контакт)"
        ]
        links: List[str] = []
        for a in soup.find_all("a", href=True):
            href = a.get("href", "").lower()
            text = a.get_text(" ", strip=True).lower()
            if any(re.search(p, f"{href} {text}") for p in patterns):
                full = urljoin(base_url, a["href"])
                if full.startswith("http"):
                    links.append(full)
        return list(dict.fromkeys(links))[:self.max_pages]

    async def crawl_one(self, clinic: RawClinic, client: httpx.AsyncClient) -> Dict[str, Any]:
        """Обрабатывает одну организацию: скачивает сайт или формирует карточку фоллбека."""
        if not clinic.site:
            card_text = (
                f"Организация: {clinic.name}. "
                f"Адрес: {clinic.address}. "
                f"Рубрики и деятельность: {', '.join(clinic.rubrics)}. "
                f"{clinic.snippet}"
            ).strip()
            return {"text": card_text, "emails": [], "status": "no_site_card"}

        html, status = await self.http_fetcher.fetch(client, clinic.site)

        # Фоллбек на Playwright при 403 / 503 / блокировках
        if (not html or "http_403" in status or "http_503" in status or len(html) < 800) and self.use_pw_fallback:
            html, status = await self.pw_fetcher.fetch(clinic.site)

        # Фоллбек на карточку, если сайт недоступен
        if not html:
            card_text = (
                f"Организация: {clinic.name}. Сайт (недоступен): {clinic.site}. "
                f"Адрес: {clinic.address}. Рубрики и деятельность: {', '.join(clinic.rubrics)}. "
                f"Описание и сниппет: {clinic.snippet}"
            ).strip()
            return {"text": card_text, "emails": [], "status": f"card_fallback_{status}"}

        soup = BeautifulSoup(html, "lxml")
        all_text = soup.get_text(separator=" ", strip=True)

        # Сбор email-адресов
        emails: Set[str] = set(re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", all_text))
        for a in soup.select('a[href^="mailto:"]'):
            emails.add(a["href"].replace("mailto:", "").split("?")[0])

        # Параллельный сбор целевых подстраниц сайта
        sublinks = self.extract_links(html, clinic.site)[:3]
        if sublinks:
            subpages_results = await asyncio.gather(
                *(self.http_fetcher.fetch(client, link) for link in sublinks)
            )
            for sub_html, _ in subpages_results:
                if sub_html:
                    sub_soup = BeautifulSoup(sub_html, "lxml")
                    all_text += " " + sub_soup.get_text(" ", strip=True)

        return {
            "text": all_text[:35000],
            "emails": list(emails)[:3],
            "status": status,
        }

    async def crawl_all(self, clinics: List[RawClinic]) -> List[Dict[str, Any]]:
        """Конкурентный краулинг пула сайтов клиник."""
        logger.info(
            f"Node 3: SmartCrawler для {len(clinics)} организаций "
            f"(concurrency={self.concurrency}, обход SSL и Punycode)..."
        )
        semaphore = asyncio.Semaphore(self.concurrency)

        async with httpx.AsyncClient(http2=True, verify=False, timeout=30) as client:
            async def worker(c: RawClinic) -> Dict[str, Any]:
                async with semaphore:
                    data = await self.crawl_one(c, client)
                    return {**c.to_dict(), **data}

            return await asyncio.gather(*(worker(c) for c in clinics))

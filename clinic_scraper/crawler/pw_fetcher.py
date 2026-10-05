"""Фоллбек-загрузчик на базе Playwright для защиты от 403, Cloudflare и SPA."""

from typing import Tuple
from diskcache import Cache

from clinic_scraper.core.logger import logger
from clinic_scraper.core.punycode import to_punycode_url, REALISTIC_HEADERS


class PlaywrightFetcher:
    """Headless браузер для рендеринга сложных динамических сайтов."""

    def __init__(self, cache: Cache):
        self.cache = cache

    async def fetch(self, url: str) -> Tuple[str, str]:
        target_url = to_punycode_url(url)
        if not target_url:
            return "", "invalid_url"

        cache_key = f"pw:{target_url}"
        if cache_key in self.cache:
            return self.cache[cache_key], "cached_pw"

        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled"]
                )
                context = await browser.new_context(
                    user_agent=REALISTIC_HEADERS["User-Agent"],
                    ignore_https_errors=True
                )
                page = await context.new_page()
                await page.goto(target_url, wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(2500)
                html = await page.content()
                await browser.close()

                if len(html) > 500:
                    self.cache[cache_key] = html
                    return html, "ok_pw"
                return "", "empty_pw"
        except Exception as e:
            logger.warning(f"Playwright fallback ошибка {url}: {e}")
            return "", "error_pw"

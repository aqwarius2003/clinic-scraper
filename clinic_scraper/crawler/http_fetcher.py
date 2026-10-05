"""Асинхронный HTTP-загрузчик страниц на базе httpx с кэшированием."""

from typing import Tuple
from diskcache import Cache
import httpx

from clinic_scraper.core.punycode import to_punycode_url, REALISTIC_HEADERS


class HttpFetcher:
    """Асинхронный HTTP-клиент с обходом SSL, антибот-заголовками и дисковым кэшем."""

    def __init__(self, cache: Cache, timeout: int = 15):
        self.cache = cache
        self.timeout = timeout

    async def fetch(self, client: httpx.AsyncClient, url: str) -> Tuple[str, str]:
        """Загружает HTML страницы или возвращает результат из кэша."""
        target_url = to_punycode_url(url)
        if not target_url:
            return "", "invalid_url"

        cache_key = f"httpx:{target_url}"
        if cache_key in self.cache:
            return self.cache[cache_key], "cached"

        try:
            headers = dict(REALISTIC_HEADERS)
            headers["Referer"] = target_url
            resp = await client.get(
                target_url,
                headers=headers,
                follow_redirects=True,
                timeout=self.timeout
            )
            if resp.status_code == 200 and len(resp.text) > 500:
                self.cache[cache_key] = resp.text
                return resp.text, "ok"
            return "", f"http_{resp.status_code}"
        except Exception as e:
            return "", f"error_{type(e).__name__}"

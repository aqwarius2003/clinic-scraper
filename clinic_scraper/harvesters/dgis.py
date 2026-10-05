"""Асинхронный сборщик организаций из 2GIS через публичный API."""

import asyncio
from typing import List, Dict, Any, Optional
import httpx

from clinic_scraper.config import AppSettings
from clinic_scraper.core.logger import logger
from clinic_scraper.core.punycode import REALISTIC_HEADERS
from clinic_scraper.harvesters.base import BaseHarvester
from clinic_scraper.models import RawClinic


class DGisHarvester(BaseHarvester):
    """Сборщик данных 2GIS с пулом публичных ключей API."""

    def __init__(self, settings: AppSettings):
        self.settings = settings
        self.city = settings.city
        self.queries = settings.search_config.search_queries
        self.stop_words = [sw.lower() for sw in settings.search_config.stop_words_gov]
        self.public_keys = settings.public_keys_2gis
        self.max_pages = settings.max_pages_2gis

    async def _fetch_page(
        self,
        client: httpx.AsyncClient,
        query: str,
        page: int,
        api_key: str
    ) -> List[Dict[str, Any]]:
        url = "https://catalog.api.2gis.com/3.0/items"
        params = {
            "q": f"{query} {self.city}",
            "page": page,
            "page_size": 50,
            "fields": "items.contact_groups,items.point,items.rubrics,items.address,items.org,items.general_info,items.schedule",
            "key": api_key,
            "locale": "ru_RU",
        }
        headers = {
            "User-Agent": REALISTIC_HEADERS["User-Agent"],
            "Referer": "https://2gis.ru/",
        }
        try:
            resp = await client.get(url, params=params, headers=headers, timeout=15)
            if resp.status_code == 200:
                return resp.json().get("result", {}).get("items", [])
        except Exception as e:
            logger.warning(f"2GIS error on query '{query}' (page {page}): {e}")
        return []

    async def _find_working_key(self, client: httpx.AsyncClient) -> Optional[str]:
        for key in self.public_keys:
            items = await self._fetch_page(client, "косметология", 1, key)
            if items:
                logger.info(f"Рабочий публичный ключ 2GIS подтвержден: {key}")
                return key
        return None

    async def harvest(self) -> List[RawClinic]:
        if not self.settings.use_2gis:
            logger.info("2GIS сбор отключен настройкой USE_2GIS=false")
            return []

        logger.info(f"→ 2GIS сбор для города: {self.city}...")
        clinics: Dict[str, RawClinic] = {}

        async with httpx.AsyncClient(http2=True, verify=False) as client:
            working_key = await self._find_working_key(client)
            if not working_key:
                logger.error("Нет доступного рабочего ключа 2GIS из списка")
                return []

            for query in self.queries:
                for page in range(1, self.max_pages + 1):
                    items = await self._fetch_page(client, query, page, working_key)
                    if not items:
                        break

                    for item in items:
                        name = item.get("name", "").strip()
                        if not name or any(sw in name.lower() for sw in self.stop_words):
                            continue

                        sid = str(item.get("id", ""))
                        if sid in clinics:
                            clinics[sid].branches_count += 1
                            continue

                        phones, site = [], ""
                        for g in item.get("contact_groups", []):
                            for c in g.get("contacts", []):
                                if c.get("type") == "phone":
                                    phones.append(c.get("value", ""))
                                elif c.get("type") == "website":
                                    site = c.get("url") or c.get("value", "")

                        snippet_parts = []
                        if item.get("general_info"):
                            snippet_parts.append(str(item["general_info"]))
                        if item.get("org", {}).get("description"):
                            snippet_parts.append(str(item["org"]["description"]))

                        clinics[sid] = RawClinic(
                            source_id=sid,
                            name=name,
                            address=item.get("address_name") or item.get("full_address_name", ""),
                            phones=phones,
                            site=site,
                            rubrics=[r.get("name", "") for r in item.get("rubrics", [])],
                            source="2gis",
                            snippet=" | ".join(snippet_parts)
                        )

                    await asyncio.sleep(0.35)

        logger.info(f"2GIS успешно собрал: {len(clinics)} уникальных организаций")
        return list(clinics.values())

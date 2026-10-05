"""Пакет сборщиков организаций (2GIS, Яндекс.Карты)."""

import asyncio
from typing import List

from clinic_scraper.config import AppSettings
from clinic_scraper.core.logger import logger
from clinic_scraper.harvesters.base import BaseHarvester
from clinic_scraper.harvesters.dgis import DGisHarvester
from clinic_scraper.harvesters.yandex import YandexHarvester
from clinic_scraper.models import RawClinic


async def harvest_all(settings: AppSettings) -> List[RawClinic]:
    """Параллельный запуск всех активных сборщиков гео-данных."""
    logger.info(f"Node 1: Запуск сбора гео-данных для города '{settings.city}'...")
    tasks = []
    if settings.use_2gis:
        tasks.append(DGisHarvester(settings).harvest())
    if settings.use_yandex:
        tasks.append(YandexHarvester(settings).harvest())

    results = await asyncio.gather(*tasks)
    all_clinics = [c for sublist in results for c in sublist]
    logger.info(f"Итого собрано с карт: {len(all_clinics)} сырых записей")
    return all_clinics


__all__ = ["BaseHarvester", "DGisHarvester", "YandexHarvester", "harvest_all"]

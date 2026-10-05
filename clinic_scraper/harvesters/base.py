"""Базовый абстрактный класс сборщиков гео-данных."""

from abc import ABC, abstractmethod
from typing import List
from clinic_scraper.models import RawClinic


class BaseHarvester(ABC):
    """Интерфейс сборщика организаций из гео-сервисов."""

    @abstractmethod
    async def harvest(self) -> List[RawClinic]:
        """Асинхронный сбор записей организаций."""
        pass

"""Пакет дедупликации записей организаций."""

from clinic_scraper.dedup.cascade import smart_cascade_dedup

__all__ = ["smart_cascade_dedup"]

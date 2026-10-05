"""Пакет краулинга сайтов клиник."""

from clinic_scraper.crawler.http_fetcher import HttpFetcher
from clinic_scraper.crawler.pw_fetcher import PlaywrightFetcher
from clinic_scraper.crawler.spider import SmartCrawler

__all__ = ["HttpFetcher", "PlaywrightFetcher", "SmartCrawler"]

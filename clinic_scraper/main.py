"""CLI точка входа ClinicScraper."""

import argparse
import asyncio
from pathlib import Path
from typing import Optional

from clinic_scraper.config import get_settings
from clinic_scraper.core.logger import logger
from clinic_scraper.pipeline import Pipeline


def parse_args():
    parser = argparse.ArgumentParser(
        prog="clinic-scraper",
        description="ClinicScraper: Модульный асинхронный сервис сбора и скоринга клиник (2GIS, Яндекс, Gemini)"
    )
    parser.add_argument(
        "--city",
        type=str,
        default=None,
        help="Город для сбора (по умолчанию берется из .env или search_config.json)"
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Путь к файлу конфигурации поиска (по умолчанию: config/search_config.json)"
    )
    parser.add_argument(
        "--force-reharvest",
        action="store_true",
        default=False,
        help="Принудительно перезапустить сбор с 2GIS и Яндекс.Карт"
    )
    parser.add_argument(
        "--force-recrawl",
        action="store_true",
        default=False,
        help="Принудительно перезапустить краулинг сайтов"
    )
    return parser.parse_args()


async def async_main(
    city: Optional[str] = None,
    config_path: Optional[str] = None,
    force_reharvest: bool = False,
    force_recrawl: bool = False
):
    cfg_p = Path(config_path) if config_path else None
    settings = get_settings(city=city, config_path=cfg_p)
    pipeline = Pipeline(settings)
    await pipeline.run(force_reharvest=force_reharvest, force_recrawl=force_recrawl)


def main():
    args = parse_args()
    asyncio.run(async_main(
        city=args.city,
        config_path=args.config,
        force_reharvest=args.force_reharvest,
        force_recrawl=args.force_recrawl
    ))


if __name__ == "__main__":
    main()

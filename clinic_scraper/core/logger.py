"""Настройка логирования ClinicScraper."""

import logging
import sys


def setup_logger(name: str = "clinic_scraper", level: int = logging.INFO) -> logging.Logger:
    """Создает и настраивает форматированный логгер."""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-7s | %(message)s",
            datefmt="%H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.propagate = False
    return logger


logger = setup_logger()

"""Умное каскадное слияние дублей организаций 2GIS и Яндекс."""

import re
from typing import List, Dict, Tuple, Optional

from clinic_scraper.config import DedupRulesConfig
from clinic_scraper.core.logger import logger
from clinic_scraper.core.punycode import (
    normalize_phone,
    phone_digits_key,
    extract_clean_domain,
    clean_brand_name,
    extract_street_keyword,
)
from clinic_scraper.models import RawClinic


def smart_cascade_dedup(
    clinics: List[RawClinic],
    dedup_rules: Optional[DedupRulesConfig] = None,
    city: str = ""
) -> List[RawClinic]:
    """Умное каскадное объединение дублей (по доменам, телефонам, бренду+улице, имени)."""
    logger.info(f"Node 2: Умное каскадное объединение ({len(clinics)} сырых записей)...")
    unique_clinics: List[RawClinic] = []

    domain_index: Dict[str, int] = {}
    phone_index: Dict[str, int] = {}
    brand_street_index: Dict[Tuple[str, str], int] = {}
    exact_name_index: Dict[str, int] = {}

    social_domains = dedup_rules.social_domains if dedup_rules else None
    aggregator_domains = dedup_rules.aggregator_domains if dedup_rules else None
    brand_stop_words = dedup_rules.brand_stop_words if dedup_rules else None
    street_stop_words = dedup_rules.street_stop_words if dedup_rules else None

    for c in clinics:
        # Нормализация номеров телефонов
        c.phones = [normalize_phone(p) for p in c.phones if p]

        match_idx: Optional[int] = None

        # 1. Сравнение по чистому домену / профилю VK / Taplink
        dom = extract_clean_domain(
            c.site,
            social_domains=social_domains,
            aggregator_domains=aggregator_domains
        )
        if dom and dom in domain_index:
            match_idx = domain_index[dom]

        # 2. Сравнение по номерам телефонов
        if match_idx is None:
            for p in c.phones:
                pkey = phone_digits_key(p)
                if len(pkey) >= 10 and pkey in phone_index:
                    match_idx = phone_index[pkey]
                    break

        # 3. Сравнение по очищенному бренду и улице
        brand = clean_brand_name(c.name, stop_words=brand_stop_words)
        street = extract_street_keyword(c.address, city=city, stop_words=street_stop_words)
        if match_idx is None and len(brand) >= 3 and street:
            key = (brand, street)
            if key in brand_street_index:
                match_idx = brand_street_index[key]

        # 4. Сравнение по точному совпадению имени
        norm_name = re.sub(r"\s+", " ", c.name.lower().strip())
        if match_idx is None and norm_name in exact_name_index:
            match_idx = exact_name_index[norm_name]

        if match_idx is not None:
            # Слияние с ранее добавленной организацией
            existing = unique_clinics[match_idx]
            if existing.source != c.source:
                existing.source = "2gis + yandex"

            # Объединяем телефоны
            for p in c.phones:
                if p not in existing.phones:
                    existing.phones.append(p)

            # Объединяем рубрики
            for r in c.rubrics:
                if r not in existing.rubrics:
                    existing.rubrics.append(r)

            # Выбираем лучший сайт (отдельный домен > соцсеть > пусто)
            if not existing.site and c.site:
                existing.site = c.site
            elif existing.site and c.site and "vk.com" in existing.site and "vk.com" not in c.site:
                existing.site = c.site

            # Выбираем более полный адрес
            if len(c.address) > len(existing.address):
                existing.address = c.address

            # Объединяем сниппеты
            if c.snippet and c.snippet not in existing.snippet:
                existing.snippet = (existing.snippet + " | " + c.snippet).strip(" | ")

            existing.branches_count = max(existing.branches_count, c.branches_count)
        else:
            new_idx = len(unique_clinics)
            unique_clinics.append(c)

            if dom:
                domain_index[dom] = new_idx
            for p in c.phones:
                pkey = phone_digits_key(p)
                if len(pkey) >= 10:
                    phone_index[pkey] = new_idx
            if len(brand) >= 3 and street:
                brand_street_index[(brand, street)] = new_idx
            if norm_name:
                exact_name_index[norm_name] = new_idx

    logger.info(
        f"Уникальных после умного слияния: {len(unique_clinics)} "
        f"(исключено {len(clinics) - len(unique_clinics)} дублей)"
    )
    return unique_clinics

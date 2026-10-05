"""Первичный regex-анализ текста сайтов по конфигурационным правилам."""

import re
from typing import Dict, List
from clinic_scraper.config import SearchConfig


class RegexFilter:
    """Быстрый пре-фильтр процедур и брендов плазмотерапии."""

    def __init__(self, search_config: SearchConfig):
        self.injection_keywords = search_config.regex_filter.injection_keywords
        self.prp_keywords = search_config.regex_filter.prp_keywords
        self.prp_brands = search_config.prp_brands

        # Компиляция общего регулярного выражения для инъекций
        if self.injection_keywords:
            inj_pattern_str = "(" + "|".join(self.injection_keywords) + ")"
            self._inj_regex = re.compile(inj_pattern_str, re.IGNORECASE)
        else:
            self._inj_regex = None

        # Компиляция регулярного выражения для PRP
        if self.prp_keywords:
            prp_pattern_str = "(" + "|".join(self.prp_keywords) + ")"
            self._prp_regex = re.compile(prp_pattern_str, re.IGNORECASE)
        else:
            self._prp_regex = None

    def analyze(self, text: str) -> Dict[str, str]:
        """Анализирует текст и возвращает статус инъекций и PRP."""
        text_l = text.lower()

        inj_found = bool(self._inj_regex.search(text_l)) if self._inj_regex else False
        prp_found = bool(self._prp_regex.search(text_l)) if self._prp_regex else False

        # Поиск упомянутых брендов плазмотерапии
        matched_brands: List[str] = []
        for brand, aliases in self.prp_brands.items():
            if any(alias.lower() in text_l for alias in aliases):
                matched_brands.append(brand)

        prp_str = "Нет"
        if prp_found:
            if matched_brands:
                prp_str = f"Да ({', '.join(matched_brands)})"
            else:
                prp_str = "Да (бренд не указан)"

        return {
            "injection_therapy": "Да" if inj_found else "Нет",
            "prp_therapy_brand": prp_str,
        }

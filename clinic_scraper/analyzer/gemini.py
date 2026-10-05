"""Асинхронный клиент Gemini API с пулом ключей, rate limiting и structured output."""

import asyncio
import json
from typing import Dict, Any

from clinic_scraper.analyzer.rate_limiter import GeminiPool
from clinic_scraper.config import AppSettings
from clinic_scraper.core.logger import logger


class GeminiAnalyzer:
    """Интеллектуальный анализатор сайтов и карточек клиник через Google Gemini."""

    def __init__(self, settings: AppSettings, pool: GeminiPool):
        self.settings = settings
        self.pool = pool
        self.prompt_template = settings.search_config.gemini.prompt_template
        self.model_name = settings.gemini_model
        self.temperature = settings.gemini_temperature
        self.max_retries = settings.gemini_max_retries
        self.backoff = settings.gemini_backoff_seconds
        self.max_prompt_chars = settings.gemini_max_prompt_chars

    async def call_gemini(self, site_text: str) -> Dict[str, Any]:
        """Отправляет текст сайта/карточки в Gemini и возвращает структурированный JSON."""
        if not self.pool.has_keys():
            return {}

        prompt = self.prompt_template.format(site_text=site_text[:self.max_prompt_chars])
        estimated_tokens = max(200, int(len(prompt) / 2.5) + 300)

        current_backoff = self.backoff

        for attempt in range(1, self.max_retries + 1):
            key, limiter = await self.pool.get_next_key_limiter()
            slot_idx = await limiter.acquire(estimated_tokens)

            try:
                import google.generativeai as genai
                genai.configure(api_key=key)
                model = genai.GenerativeModel(self.model_name)

                response = await asyncio.to_thread(
                    model.generate_content,
                    prompt,
                    generation_config={
                        "temperature": self.temperature,
                        "response_mime_type": "application/json",
                    }
                )

                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    total_tokens = getattr(response.usage_metadata, "total_token_count", None)
                    if total_tokens:
                        limiter.update_tokens(slot_idx, total_tokens)

                return json.loads(response.text)
            except Exception as e:
                err_msg = str(e).lower()
                if any(term in err_msg for term in ("429", "resource_exhausted", "quota", "rate limit")):
                    if attempt < self.max_retries:
                        logger.warning(
                            f"Gemini пауза/квота (попытка {attempt}/{self.max_retries}): {e}. "
                            f"Пауза {current_backoff}с..."
                        )
                        await asyncio.sleep(current_backoff)
                        current_backoff *= 2
                        continue
                logger.warning(f"Gemini ошибка генерации: {e}")
                return {}

        return {}

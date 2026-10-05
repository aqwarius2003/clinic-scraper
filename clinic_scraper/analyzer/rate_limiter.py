"""Скользящий rate limiter и многоключевой пул для Google Gemini API."""

import asyncio
import time
from typing import List, Tuple


class KeyRateLimiter:
    """Ограничитель частоты запросов для конкретного ключа Gemini."""

    def __init__(self, key: str, rpm: int = 14, tpm: int = 250000, min_interval: float = 4.2):
        self.key = key
        self.rpm = rpm
        self.tpm = tpm
        self.min_interval = min_interval
        self.last_call_time = 0.0
        self.lock = asyncio.Lock()
        self.history: List[List[float]] = []

    def _purge(self, now: float) -> None:
        cutoff = now - 60.0
        self.history = [rec for rec in self.history if rec[0] > cutoff]

    async def acquire(self, estimated_tokens: int) -> int:
        """Резервирует слот на отправку запроса с соблюдением RPM, TPM и min_interval."""
        async with self.lock:
            while True:
                now = time.monotonic()
                self._purge(now)

                wait_interval = max(0.0, self.min_interval - (now - self.last_call_time))

                wait_rpm = 0.0
                if len(self.history) >= self.rpm:
                    oldest_ts = self.history[0][0]
                    wait_rpm = max(0.0, 60.0 - (now - oldest_ts) + 0.1)

                wait_tpm = 0.0
                current_tokens = sum(rec[1] for rec in self.history)
                if current_tokens + estimated_tokens > self.tpm:
                    needed_to_free = (current_tokens + estimated_tokens) - self.tpm
                    freed = 0.0
                    for ts, tok in self.history:
                        freed += tok
                        if freed >= needed_to_free:
                            wait_tpm = max(0.0, 60.0 - (now - ts) + 0.1)
                            break

                wait_time = max(wait_interval, wait_rpm, wait_tpm)
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                else:
                    self.last_call_time = time.monotonic()
                    rec = [self.last_call_time, float(estimated_tokens)]
                    self.history.append(rec)
                    return len(self.history) - 1

    def update_tokens(self, index: int, actual_tokens: int) -> None:
        """Корректирует фактический расход токенов по ответу Gemini usage_metadata."""
        if 0 <= index < len(self.history):
            self.history[index][1] = float(actual_tokens)


class GeminiPool:
    """Пул API-ключей Gemini с равномерной ротацией (Round-Robin)."""

    def __init__(self, keys: List[str], rpm: int = 14, tpm: int = 250000):
        self.keys = keys
        min_interval = max(1.0, 60.0 / rpm + 0.1)
        self.limiters = [
            KeyRateLimiter(k, rpm=rpm, tpm=tpm, min_interval=min_interval)
            for k in keys
        ]
        self._current_idx = 0
        self._lock = asyncio.Lock()

    def has_keys(self) -> bool:
        return len(self.keys) > 0

    async def get_next_key_limiter(self) -> Tuple[str, KeyRateLimiter]:
        """Возвращает следующий ключ и его персональный ограничитель."""
        async with self._lock:
            limiter = self.limiters[self._current_idx]
            self._current_idx = (self._current_idx + 1) % len(self.limiters)
            return limiter.key, limiter

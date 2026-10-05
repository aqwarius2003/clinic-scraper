"""Главный асинхронный пайплайн ClinicScraper."""

import asyncio
import json
import signal
import sys
import time
from typing import List, Dict, Any

from clinic_scraper.analyzer.gemini import GeminiAnalyzer
from clinic_scraper.analyzer.rate_limiter import GeminiPool
from clinic_scraper.analyzer.regex_filter import RegexFilter
from clinic_scraper.config import AppSettings
from clinic_scraper.core.logger import logger
from clinic_scraper.crawler.spider import SmartCrawler
from clinic_scraper.dedup.cascade import smart_cascade_dedup
from clinic_scraper.exporters.excel import export_to_excel
from clinic_scraper.harvesters import harvest_all
from clinic_scraper.models import RawClinic, ClinicRecord


class Pipeline:
    """Оркестратор полного цикла сбора, обогащения и анализа клиник."""

    def __init__(self, settings: AppSettings):
        self.settings = settings
        self.city_default = settings.search_config.city
        self.checkpoint_interval = settings.pipeline.checkpoint_interval

        self.raw_file = settings.data_dir / f"raw_clinics_{settings.city}.json"
        self.crawled_file = settings.data_dir / f"crawled_sites_{settings.city}.json"
        self.checkpoint_file = settings.data_dir / f"analyzed_checkpoint_{settings.city}.json"

        # Обратная совместимость с ранее собранными файлами дефолтного города
        if not self.raw_file.exists() and (settings.data_dir / "raw_clinics.json").exists() and settings.city == self.city_default:
            self.raw_file = settings.data_dir / "raw_clinics.json"
        if not self.crawled_file.exists() and (settings.data_dir / "crawled_sites.json").exists() and settings.city == self.city_default:
            self.crawled_file = settings.data_dir / "crawled_sites.json"
        if not self.checkpoint_file.exists() and (settings.data_dir / "analyzed_checkpoint.json").exists() and settings.city == self.city_default:
            self.checkpoint_file = settings.data_dir / "analyzed_checkpoint.json"

        self.output_excel = settings.output_dir / f"{settings.city}_Клиники_Пилот.xlsx"

        self.pool = GeminiPool(
            keys=settings.gemini_api_keys,
            rpm=settings.gemini.rpm,
            tpm=settings.gemini.tpm,
        )
        self.gemini_analyzer = GeminiAnalyzer(settings, self.pool)
        self.regex_filter = RegexFilter(settings.search_config)
        self.spider = SmartCrawler(settings)

    def load_checkpoint(self) -> Dict[str, dict]:
        """Загружает сохраненный прогресс анализа."""
        if self.checkpoint_file.exists():
            try:
                with open(self.checkpoint_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    logger.info(f"Загружен чекпоинт: {len(data)} клиник уже проанализировано")
                    return data
            except Exception as e:
                logger.warning(f"Ошибка загрузки чекпоинта: {e}")
        return {}

    def save_checkpoint(self, checkpoint: Dict[str, dict]) -> None:
        """Сохраняет текущий прогресс на диск."""
        try:
            with open(self.checkpoint_file, "w", encoding="utf-8") as f:
                json.dump(checkpoint, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Ошибка сохранения чекпоинта: {e}")

    async def run_harvester(self, force_reharvest: bool = False) -> List[RawClinic]:
        """Узел 1 & 2: GeoHarvest и каскадная дедупликация."""
        if self.raw_file.exists() and not force_reharvest:
            logger.info(f"Используем кэшированные гео-данные из {self.raw_file}")
            with open(self.raw_file, "r", encoding="utf-8") as f:
                raw_items = [RawClinic.from_dict(item) for item in json.load(f)]
            return smart_cascade_dedup(
                raw_items,
                dedup_rules=self.settings.search_config.dedup_rules,
                city=self.settings.city
            )

        raw = await harvest_all(self.settings)
        cleaned = smart_cascade_dedup(
            raw,
            dedup_rules=self.settings.search_config.dedup_rules,
            city=self.settings.city
        )
        with open(self.raw_file, "w", encoding="utf-8") as f:
            json.dump([c.to_dict() for c in cleaned], f, ensure_ascii=False, indent=2)
        logger.info(f"Гео-данные сохранены в {self.raw_file}")
        return cleaned

    async def run_crawler(self, clinics: List[RawClinic], force_recrawl: bool = False) -> List[Dict[str, Any]]:
        """Узел 3: SmartCrawler."""
        if self.crawled_file.exists() and not force_recrawl:
            logger.info(f"Используем кэшированные сайты из {self.crawled_file}")
            with open(self.crawled_file, "r", encoding="utf-8") as f:
                return json.load(f)

        crawled = await self.spider.crawl_all(clinics)
        with open(self.crawled_file, "w", encoding="utf-8") as f:
            json.dump(crawled, f, ensure_ascii=False, indent=2)
        logger.info(f"Сайты сохранены в {self.crawled_file}")
        return crawled

    async def run_analyzer(self, crawled: List[Dict[str, Any]]) -> List[ClinicRecord]:
        """Узел 4: HybridAnalyzer с конкурентной обработкой и потокобезопасным чекпоинтом."""
        logger.info("Node 4: HybridAnalyzer (параллельный скоринг сайтов и карточек)...")
        checkpoint = self.load_checkpoint()
        records_map: Dict[str, ClinicRecord] = {}
        total = len(crawled)
        lock = asyncio.Lock()
        completed_counter = 0

        # Восстановление ранее обработанных записей из чекпоинта
        for i, item in enumerate(crawled, 1):
            sid = item.get("source_id", f"c_{i}")
            if sid in checkpoint:
                rec_dict = dict(checkpoint[sid])
                rec_dict["№ п/п"] = i
                records_map[sid] = ClinicRecord(**rec_dict)

        def sigint_handler(signum, frame):
            logger.warning(
                f"\n[Ctrl+C] Прерывание процесса! Экстренное сохранение {len(records_map)} записей..."
            )
            self.save_checkpoint(checkpoint)
            export_to_excel(list(records_map.values()), self.output_excel)
            sys.exit(0)

        original_handler = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, sigint_handler)

        semaphore = asyncio.Semaphore(self.settings.gemini.concurrency)

        async def process_one(idx: int, item: Dict[str, Any]) -> None:
            nonlocal completed_counter
            sid = item.get("source_id", f"c_{idx}")

            if sid in records_map:
                return

            text = item.get("text", "")
            status = item.get("status", "ok")

            # 1. Быстрый первичный regex-фильтр
            reg = self.regex_filter.analyze(text)
            injection = reg["injection_therapy"]
            prp_brand = reg["prp_therapy_brand"]
            specialists = "Требует уточнения"
            note = ""

            # 2. Вызов Gemini при наличии контента
            if text and len(text) > 30 and self.pool.has_keys():
                async with semaphore:
                    gem = await self.gemini_analyzer.call_gemini(text)
                    if gem:
                        if gem.get("injection_therapy") in ("Да", "Нет"):
                            injection = gem["injection_therapy"]
                        if gem.get("prp_therapy") == "Да":
                            brands = gem.get("prp_brands") or []
                            prp_brand = f"Да ({', '.join(brands)})" if brands else "Да (бренд не указан)"
                        elif gem.get("prp_therapy") == "Нет":
                            prp_brand = "Нет"
                        sc = gem.get("specialists_count")
                        specialists = str(sc) if sc is not None else "Требует уточнения"
                        note = str(gem.get("specialists_comment", ""))[:150]

            if "card_fallback" in status:
                note = f"По карточке (сайт не ответил): {note}" if note else "По карточке (сайт не ответил)"
            elif status == "no_site_card":
                note = f"По карточке (без сайта): {note}" if note else "По карточке (без сайта)"

            record = ClinicRecord(
                index=idx,
                name=item["name"],
                branches_count=item.get("branches_count", 1),
                activity=", ".join(item.get("rubrics", [])),
                phone=item["phones"][0] if item.get("phones") else "",
                email=(item.get("emails") or [""])[0],
                site=item.get("site", ""),
                specialists_count=specialists,
                injection_therapy=injection,
                prp_therapy_brand=prp_brand,
                status=status,
                note=note,
                source=item.get("source", ""),
                source_id=sid
            )

            async with lock:
                records_map[sid] = record
                checkpoint[sid] = record.model_dump(by_alias=True)
                completed_counter += 1
                curr = len(records_map)

                logger.info(
                    f"[{curr}/{total}] ({curr/total*100:.1f}%) {record.name[:30]:<30} | "
                    f"Инъекции: {injection:<5} | PRP: {prp_brand}"
                )

                if completed_counter % self.checkpoint_interval == 0:
                    self.save_checkpoint(checkpoint)
                    export_to_excel(list(records_map.values()), self.output_excel)

        try:
            tasks = [process_one(i, item) for i, item in enumerate(crawled, 1)]
            await asyncio.gather(*tasks)
        finally:
            signal.signal(signal.SIGINT, original_handler)
            self.save_checkpoint(checkpoint)

        # Сортировка записей по индексу порядка
        ordered_records = [
            records_map[item.get("source_id", f"c_{i}")]
            for i, item in enumerate(crawled, 1)
            if item.get("source_id", f"c_{i}") in records_map
        ]
        return ordered_records

    async def run(self, force_reharvest: bool = False, force_recrawl: bool = False) -> List[ClinicRecord]:
        """Полный запуск пайплайна."""
        start = time.time()
        logger.info("=" * 65)
        logger.info(f"ЗАПУСК ПАЙПЛАЙНА CLINIC_SCRAPER ({self.settings.city.upper()})")
        logger.info(f"Пул Gemini ключей: {len(self.settings.gemini_api_keys)} шт. | Модель: {self.settings.gemini.model}")
        logger.info(f"Конкурентность анализа: {self.settings.gemini.concurrency} потоков")
        logger.info(f"Интервал сохранения чекпоинта: каждые {self.checkpoint_interval} клиник")
        logger.info("=" * 65)

        cleaned = await self.run_harvester(force_reharvest=force_reharvest)
        crawled = await self.run_crawler(cleaned, force_recrawl=force_recrawl)
        analyzed = await self.run_analyzer(crawled)
        saved_file = export_to_excel(analyzed, self.output_excel)

        target_count = sum(1 for r in analyzed if r.injection_therapy == "Да")
        logger.info("=" * 65)
        logger.info(f"ГОТОВО за {time.time() - start:.1f} сек.")
        logger.info(f"Всего клиник в базе: {len(analyzed)}")
        logger.info(f"Целевых с инъекционной терапией: {target_count}")
        logger.info(f"Файл сохранен: {saved_file}")
        logger.info("=" * 65)
        return analyzed

# ClinicScraper 🏥💉

**ClinicScraper** — высокопроизводительный модульный асинхронный сервис сбора, краулинга сайтов и AI-скоринга медицинских центров и косметологических клиник под задачи вывода препаратов на рынок РФ (B2B лидогенерация и маркетинговый аудит).

---

## 🚀 Возможности и ключевые фичи

- **Мульти-источниковый гео-сбор:**
  - Асинхронный клиент **2GIS API** с поддержкой ротации пула публичных ключей.
  - Автоматизированный headless-сборщик **Яндекс.Карт** на базе Playwright с эмуляцией пользовательского скролла.
- **Умная 4-уровневая каскадная дедупликация:**
  - Склейка карточек 2GIS и Яндекса по чистым доменам/профилям соцсетей (VK, Taplink, T.me).
  - Склейка по нормализованным номерам телефонов (`+7...`).
  - Склейка по очищенному названию бренда (без ООО, ИП, префиксов) + ключевому слову улицы.
  - Слияние по нормализованному точному наименованию.
- **Отказоустойчивый краулинг сайтов (SmartCrawler):**
  - Поддержка русских доменов (`.рф` / Punycode IDN).
  - Обход проблем с российскими сертификатами Минцифры/НУЦ РФ (`verify=False`).
  - Защита от бот-блокировок с реалистичными Chromium-заголовками.
  - Дисковое кэширование страниц (`diskcache`).
  - Параллельный сбор целевых подстраниц (прайс-листы, специалисты, контакты).
  - Бесшовный фоллбек на Playwright при ошибках `403 / 503 / Cloudflare / SPA`.
  - Фоллбек на сниппеты и рубрики гео-карточки при отсутствии или недоступности сайта.
- **Гибридный скоринг (Regex + Google Gemini):**
  - Быстрый первичный regex-фильтр целевых процедур и PRP-брендов.
  - Пул API-ключей Google Gemini (`GeminiPool`) с распределением Round-Robin.
  - Скользящий rate limiter для соблюдения бесплатных и платных квот (RPM/TPM).
  - Конкурентная обработка клиник через `asyncio.Semaphore` с защитой чекпоинтов через `asyncio.Lock`.
- **Отказоустойчивость и безопасность данных (Resume Capability):**
  - Промежуточное автосохранение чекпоинтов на диск каждые 15 клиник.
  - Перехват прерывания `Ctrl+C` (SIGINT) с экстренным сбросом прогресса в JSON и резервный Excel.
- **Презентационная выгрузка в Excel (openpyxl):**
  - Лист 1: «Целевые клиники (Инъекции Да)» — основной квалифицированный реестр.
  - Лист 2: «Все организации (Архив)» — полный охват собранных организаций города.
  - Фирменное цветовое оформление, закрепление шапки, автоподбор ширины колонок.

---

## 🏗 Архитектура пайплайна

```
[Node 1: GeoHarvest] ──> [Node 2: CascadeDedup] ──> [Node 3: SmartCrawler] ──> [Node 4: HybridAnalyzer] ──> [Node 5: Exporter]
  (2GIS + Yandex)          (Домен, Тел, Бренд)         (httpx + Playwright)         (Regex + GeminiPool)         (Excel openpyxl)
         │                         │                           │                           │
  data/raw_clinics.json    data/raw_clinics.json       data/crawled_sites.json    data/analyzed_checkpoint.json
```

---

## 📁 Структура проекта

```text
kliniki/
├── config/
│   └── search_config.json        # Поисковые запросы, стоп-слова, regex-правила и промпты Gemini
├── clinic_scraper/
│   ├── __init__.py               # Экспорт версии
│   ├── config.py                 # Pydantic Settings (.env + search_config.json)
│   ├── models.py                 # Pydantic v2 модели (RawClinic, ClinicRecord, AnalysisResult)
│   ├── pipeline.py               # Асинхронный оркестратор 5 фаз пайплайна
│   ├── main.py                   # Полнофункциональный CLI (argparse)
│   ├── core/
│   │   ├── logger.py             # Форматированное логирование
│   │   └── punycode.py           # IDN/Punycode, нормализация телефонов и очистка брендов
│   ├── harvesters/
│   │   ├── base.py               # Интерфейс BaseHarvester
│   │   ├── dgis.py               # Асинхронный клиент 2GIS с пулом публичных ключей
│   │   └── yandex.py             # Playwright сборщик Яндекс.Карт
│   ├── dedup/
│   │   └── cascade.py            # Каскадное слияние дублей
│   ├── crawler/
│   │   ├── http_fetcher.py       # Httpx с обходом SSL и дисковым кэшем
│   │   ├── pw_fetcher.py         # Playwright фоллбек для SPA и 403
│   │   └── spider.py             # Параллельный краулер страниц прайсов и врачей
│   ├── analyzer/
│   │   ├── rate_limiter.py       # Скользящий rate limiter (RPM/TPM) и GeminiPool
│   │   ├── regex_filter.py       # Быстрый фильтр процедур и брендов PRP
│   │   └── gemini.py             # Клиент Gemini со structured output и retry backoff
│   └── exporters/
│       └── excel.py              # Стилизованная выгрузка Excel (2 листа)
├── tests/
│   ├── test_config.py            # Тесты загрузки конфигурации
│   ├── test_dedup.py             # Тесты каскадного слияния
│   ├── test_punycode.py          # Тесты нормализации телефонов, доменов и брендов
│   └── test_regex_filter.py      # Тесты детекции инъекций и PRP-брендов
├── run.py                        # Точка быстрого запуска
├── pyproject.toml                # Зависимости Poetry и настройки pytest
├── .env.example                  # Пример конфигурации секретов
└── .gitignore                    # Защита секретов, кэша, данных и чекпоинтов
```

---

## ⚙️ Установка и настройка

### 1. Требования
- Python `>= 3.10`
- [Poetry](https://python-poetry.org/)

### 2. Клонирование и установка зависимостей
```bash
poetry install
poetry run playwright install chromium
```

### 3. Настройка переменных окружения
Скопируйте пример окружения:
```bash
cp .env.example .env
```

Заполните параметры в `.env`:
```ini
# Gemini API Keys (один ключ или несколько через запятую для параллельной ротации)
GEMINI_API_KEYS=AIzaSyA...,AIzaSyB...,AIzaSyC...

# 2GIS Public API Keys (через запятую)
PUBLIC_KEYS_2GIS=ruzhub8994,rurbbn3446,ruregt3044

# Источники данных
USE_2GIS=true
USE_YANDEX=true

# Параметры города и модели
CITY=Хабаровск
GEMINI_MODEL=gemini-3.1-flash-lite
GEMINI_RPM=14
GEMINI_TPM=250000
GEMINI_CONCURRENCY=4

# Настройки краулера
CRAWLER_CONCURRENCY=8
CRAWLER_TIMEOUT=15
CRAWLER_MAX_PAGES=4
USE_PLAYWRIGHT_FALLBACK=true
```

---

## 🎯 Конфигурация бизнес-правил (`config/search_config.json`)

Вся предметная логика отделена от кода в [`config/search_config.json`](file:///d:/kliniki/config/search_config.json):
- **`search_queries`**: список направлений поиска («косметология», «пародонтология», «ортопедия», «гинекология»...).
- **`stop_words_gov`**: фильтр для исключения государственных бюджетных учреждений («гбуз», «госпиталь», «поликлиника №»...).
- **`prp_brands`**: перечень целевых брендов и пробирок (`Cortexil`, `RegenLab`, `Plasmolifting`, `Endoret`, `Medical Case`, `Ycellbio`, `T-Lab`).
- **`regex_filter`**: шаблоны процедур (биоревитализация, ботокс, филлеры, блокады, инъекции в десны/суставы).
- **`gemini.prompt_template`**: системная инструкция эксперта-аудитора с критериями классификации.

---

## 🚦 Использование

### Запуск по умолчанию (город из .env или конфига):
```bash
poetry run python run.py
```

### Запуск для конкретного города:
```bash
poetry run python run.py --city "Владивосток"
```

### Принудительный перезапуск фаз (сброс кэша):
```bash
# Пересобрать организации с карт (2GIS + Яндекс):
poetry run python run.py --city "Хабаровск" --force-reharvest

# Перескачать сайты (краулинг заново):
poetry run python run.py --city "Хабаровск" --force-recrawl
```

### Запуск через модуль пакета:
```bash
poetry run python -m clinic_scraper.main --help
```

---

## 🧪 Запуск тестов

Проект покрыт автоматическими тестами `pytest` (конфигурация, нормализация punycode/телефонов, каскадная дедупликация, regex-скоринг):
```bash
poetry run pytest -v
```

---

## 📊 Выходной результат

Итоговая таблица сохраняется в `output/<Город>_Клиники_Пилот.xlsx` и содержит:

| № п/п | Название | кол-во филиалов | Деятельность | Контакт номер | Email | Сайт | Кол-во спецов | Инъекционная терапия | Плазмотерапия (бренд) |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Клиника Эстетики | 1 | Косметология | +7 (421) 211-22-33 | info@site.ru | site.ru | 6 | Да | Да (Cortexil) |

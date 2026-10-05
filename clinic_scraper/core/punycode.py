"""Сетевые заголовки, punycode-трансляция и нормализаторы контактов."""

import re
from typing import Dict
from urllib.parse import urlparse, quote

REALISTIC_HEADERS: Dict[str, str] = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}


def to_punycode_url(url: str) -> str:
    """Конвертирует русские домены (.рф) в Punycode для корректной работы сетевых библиотек."""
    if not url:
        return ""
    try:
        url = url.strip()
        if not re.match(r"^https?://", url, re.IGNORECASE):
            url = f"http://{url}"
        parsed = urlparse(url)
        host = parsed.netloc
        if host:
            port = ""
            if ":" in host:
                host, port = host.split(":", 1)
                port = f":{port}"
            encoded_host = host.encode("idna").decode("ascii")
            netloc = f"{encoded_host}{port}"
            path = quote(parsed.path, safe="/:?#[]@!$&'()*+,;=")
            query = f"?{parsed.query}" if parsed.query else ""
            return f"{parsed.scheme}://{netloc}{path}{query}"
    except Exception:
        pass
    return url


def normalize_phone(phone: str) -> str:
    """Форматирует телефон в канонический вид +7 (XXX) XXX-XX-XX."""
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]
    elif digits.startswith("9") and len(digits) == 10:
        digits = "7" + digits
    if len(digits) == 11 and digits.startswith("7"):
        return f"+7 ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:]}"
    return phone


def phone_digits_key(phone: str) -> str:
    """Возвращает нормализованную строку цифр для индекса дедупликации."""
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]
    elif digits.startswith("9") and len(digits) == 10:
        digits = "7" + digits
    return digits


def extract_clean_domain(url: str) -> str:
    """Извлекает чистый домен или путь к профилю (VK, Taplink, T.me) для каскадной дедупликации."""
    if not url:
        return ""
    try:
        url_lower = url.lower().strip()
        parsed = urlparse(url_lower if "://" in url_lower else f"http://{url_lower}")
        host = parsed.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        try:
            host = host.encode("idna").decode("ascii")
        except Exception:
            pass
        if any(soc in host for soc in ["vk.com", "taplink.cc", "t.me"]):
            path = parsed.path.rstrip("/").lower()
            return f"{host}{path}"
        if any(agg in host for agg in ["2gis", "yandex", "zoon", "prodoctorov", "doctu", "yell"]):
            return ""
        return host
    except Exception:
        return ""


def clean_brand_name(name: str) -> str:
    """Очищает наименование от форм собственности и типовых медицинских префиксов."""
    s = name.lower()
    s = re.sub(r"[«»\"'“”„`]", " ", s)
    s = re.sub(
        r"\b(ооо|зао|пао|ао|ип|клиника|клиники|центр|сеть|салон|салоны|красоты|медицинский|медицинская|медицинские|"
        r"эстетическая|эстетической|эстетическ|эстетик|"
        r"стоматология|стоматологии|стоматологическая|косметология|косметологии|косметологическая|кабинет|доктор|врач|отделение)\b",
        " ",
        s
    )
    s = re.sub(r"\s+", " ", s).strip()
    return s


def extract_street_keyword(address: str, city: str = "") -> str:
    """Выделяет ключевое слово улицы для объединения филиалов/дублей по адресу."""
    if not address:
        return ""
    addr_l = address.lower()
    city_tokens = [c.lower() for c in re.split(r"[\s,-]+", city) if len(c) > 2] if city else []
    city_pattern = r"|".join(re.escape(c) for c in city_tokens) if city_tokens else r"хабаровск"
    addr_l = re.sub(
        rf"\b(г\.|город|{city_pattern}|ул\.|улица|пр-кт|проспект|пер\.|переулок|д\.|дом|к\.|корпус|оф\.|офис|литер|эт\.|этаж)\b",
        " ",
        addr_l
    )
    tokens = [t for t in re.split(r"[\s,]+", addr_l) if len(t) > 3 and not t.isdigit()]
    return tokens[0] if tokens else ""


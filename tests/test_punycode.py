"""Тесты Punycode, URL-экстракторов и нормализации телефонов."""

from clinic_scraper.core.punycode import (
    to_punycode_url,
    normalize_phone,
    phone_digits_key,
    extract_clean_domain,
    clean_brand_name,
    extract_street_keyword
)


def test_to_punycode_url():
    # Русские домены
    url_rf = "http://клиника-хабаровск.рф/prices"
    res = to_punycode_url(url_rf)
    assert "xn--" in res
    assert "/prices" in res

    # Обычные домены
    assert to_punycode_url("https://example.com/test") == "https://example.com/test"


def test_normalize_phone():
    assert normalize_phone("8 (4212) 11-22-33") == "+7 (421) 211-22-33"
    assert normalize_phone("+74212998877") == "+7 (421) 299-88-77"
    assert normalize_phone("9141234567") == "+7 (914) 123-45-67"


def test_phone_digits_key():
    assert phone_digits_key("+7 (4212) 11-22-33") == "74212112233"
    assert phone_digits_key("84212112233") == "74212112233"


def test_extract_clean_domain():
    assert extract_clean_domain("https://www.my-clinic.ru/about/") == "my-clinic.ru"
    assert extract_clean_domain("https://vk.com/dr_ivanov?ref=1") == "vk.com/dr_ivanov"
    assert extract_clean_domain("https://taplink.cc/beauty_khv") == "taplink.cc/beauty_khv"
    # Агрегаторы отсекаются
    assert extract_clean_domain("https://2gis.ru/khabarovsk/firm/1234") == ""
    assert extract_clean_domain("https://yandex.ru/maps/org/5678") == ""


def test_clean_brand_name():
    assert clean_brand_name("ООО «Медицинский центр Доктор Плюс»") == "плюс"
    assert clean_brand_name("Клиника эстетической косметологии Аура") == "аура"


def test_extract_street_keyword():
    assert extract_street_keyword("г. Хабаровск, ул. Ленина, д. 42") == "ленина"
    assert extract_street_keyword("пр-кт 60-летия Октября, 150") == "60-летия"

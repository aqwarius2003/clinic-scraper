"""Тесты каскадной дедупликации организаций."""

from clinic_scraper.dedup.cascade import smart_cascade_dedup
from clinic_scraper.models import RawClinic


def test_dedup_by_domain():
    c1 = RawClinic(
        source_id="2gis_1",
        name="Клиника Аура",
        phones=["+7 (4212) 11-22-33"],
        site="https://aura-khv.ru",
        source="2gis"
    )
    c2 = RawClinic(
        source_id="ya_2",
        name="Аура Мед",
        phones=["+7 (4212) 44-55-66"],
        site="http://www.aura-khv.ru/contacts",
        source="yandex"
    )
    res = smart_cascade_dedup([c1, c2])
    assert len(res) == 1
    assert res[0].source == "2gis + yandex"
    assert len(res[0].phones) == 2


def test_dedup_by_phone():
    c1 = RawClinic(
        source_id="2gis_1",
        name="Эстетик Лайн",
        phones=["8 (4212) 77-88-99"],
        site="",
        source="2gis"
    )
    c2 = RawClinic(
        source_id="ya_2",
        name="Центр Эстетик Лайн",
        phones=["+7 (4212) 77-88-99"],
        site="https://estetic.ru",
        source="yandex"
    )
    res = smart_cascade_dedup([c1, c2])
    assert len(res) == 1
    assert res[0].site == "https://estetic.ru"


def test_dedup_by_brand_and_street():
    c1 = RawClinic(
        source_id="2gis_1",
        name="ООО «Сакура»",
        address="г. Хабаровск, ул. Тургенева, 45",
        phones=[],
        site="",
        source="2gis"
    )
    c2 = RawClinic(
        source_id="ya_2",
        name="Косметология Сакура",
        address="ул. Тургенева, д. 45, оф. 12",
        phones=[],
        site="",
        source="yandex"
    )
    res = smart_cascade_dedup([c1, c2])
    assert len(res) == 1
    assert "Тургенева" in res[0].address

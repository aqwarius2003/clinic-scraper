"""Тесты регулярных выражений и детекции брендов PRP."""

from clinic_scraper.analyzer.regex_filter import RegexFilter
from clinic_scraper.config import load_search_config


def test_regex_filter_injections():
    cfg = load_search_config()
    rf = RegexFilter(cfg)

    # Положительные тесты на инъекции
    res1 = rf.analyze("У нас проводится биоревитализация гиалуроновой кислотой и ботокс.")
    assert res1["injection_therapy"] == "Да"

    res2 = rf.analyze("Лечение пародонтита: плазмолифтинг десен и инъекции в сосочки.")
    assert res2["injection_therapy"] == "Да"

    # Отрицательный тест
    res3 = rf.analyze("Лечение кариеса, чистка зубов ультразвуком, установка пломб.")
    assert res3["injection_therapy"] == "Нет"


def test_regex_filter_prp_brands():
    cfg = load_search_config()
    rf = RegexFilter(cfg)

    res1 = rf.analyze("Плазмотерапия суставов по технологии Cortexil PRP.")
    assert "Да" in res1["prp_therapy_brand"]
    assert "Cortexil" in res1["prp_therapy_brand"]

    res2 = rf.analyze("Проводим аутоплазмотерапию и PRP-терапию.")
    assert res2["prp_therapy_brand"] == "Да (бренд не указан)"

    res_pl = rf.analyze("Лечебный плазмолифтинг.")
    assert "Plasmolifting" in res_pl["prp_therapy_brand"]

    res3 = rf.analyze("Консультация терапевта, ЭКГ.")
    assert res3["prp_therapy_brand"] == "Нет"

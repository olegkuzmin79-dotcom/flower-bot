"""Validation helpers tests. Run: python test_validation.py"""
from __future__ import annotations

from utils import (
    compose_delivery_address,
    normalize_phone,
    validate_celebration_date,
    validate_customer_name,
    validate_delivery_address,
    validate_delivery_time,
    validate_delivery_time_custom,
    validate_person_name,
    validate_russian_mobile,
    validate_street_name,
    validate_building,
    build_celebration_date,
)


def test_names() -> None:
    assert validate_person_name("Катя") == "Катя"
    assert validate_person_name("Тома2341") is None
    assert validate_person_name("jlkjll") is None
    assert validate_person_name("а") is None
    print("OK names")


def test_dates() -> None:
    assert validate_celebration_date("25.10") == "25-10"
    assert validate_celebration_date("31.02") is None
    assert validate_celebration_date("32.01") is None
    assert validate_celebration_date("25-10") is None
    assert validate_celebration_date("25/10") is None
    print("OK dates")


def test_addresses() -> None:
    assert validate_delivery_address("ул. Преображенский Вал, д. 12, кв. 45")
    assert validate_delivery_address("преображенка") is None
    assert compose_delivery_address("ЦАО", "Тверская", "12", "45")
    assert compose_delivery_address(None, "Тверская", "12", None, "2")
    assert compose_delivery_address("", "Тверская", "12", "45") == "Москва, ул. Тверская, д. 12, кв. 45"
    assert compose_delivery_address("ЦАО", "ab", "12", None) is None
    print("OK addresses")


def test_structured_address() -> None:
    assert validate_street_name("Преображенский Вал")
    assert validate_street_name("ab") is None
    assert validate_building("12к2")
    assert validate_building("дом") is None
    assert build_celebration_date(25, 10) == "25-10"
    assert build_celebration_date(31, 2) is None
    print("OK structured")


def test_delivery_time() -> None:
    assert validate_delivery_time("08:00–12:00") == "08:00–12:00"
    assert validate_delivery_time_custom("08:00–12:00") == "08:00–12:00"
    assert validate_delivery_time("20ук, ка") is None
    assert validate_delivery_time("12:00-08:00") is None
    print("OK delivery time")


def test_customer_name() -> None:
    assert validate_customer_name("Иванов Иван Иванович") == "Иванов Иван Иванович"
    assert validate_customer_name("Роман") is None
    assert validate_customer_name("Роман Петр") is None
    assert validate_customer_name("jlkjll jlkjll jlkjll") is None
    print("OK customer name")


def test_phones() -> None:
    assert validate_russian_mobile("+7 916 123-45-67") == "+79161234567"
    assert validate_russian_mobile("89161234567") == "+79161234567"
    assert validate_russian_mobile("+7 495 123-45-67") is None
    assert normalize_phone("123") is None
    print("OK phones")


def test_delivery_timing() -> None:
    from datetime import date

    from utils import (
        days_until,
        delivery_possible_this_year,
        delivery_warning_message,
        save_celebration_flash_message,
    )

    ref = date(2026, 6, 15)
    assert delivery_possible_this_year("20-06", ref) is True
    assert delivery_possible_this_year("19-06", ref) is False
    assert days_until("20-06", ref) == 5
    assert "следующ" in delivery_warning_message("19-06", ref)
    assert "следующ" in save_celebration_flash_message("19-06")
    assert save_celebration_flash_message("20-06") == "Сохранено"
    print("OK delivery timing")


if __name__ == "__main__":
    test_names()
    test_dates()
    test_addresses()
    test_structured_address()
    test_delivery_time()
    test_customer_name()
    test_phones()
    test_delivery_timing()
    print("\nAll validation checks passed.")

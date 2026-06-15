"""Validation helpers tests. Run: python test_validation.py"""
from __future__ import annotations

from utils import (
    normalize_phone,
    validate_celebration_date,
    validate_delivery_address,
    validate_delivery_time,
    validate_person_name,
)


def test_names() -> None:
    assert validate_person_name("Катя") == "Катя"
    assert validate_person_name("Тома2341") is None
    assert validate_person_name("а") is None
    print("OK names")


def test_dates() -> None:
    assert validate_celebration_date("25.10") == "25-10"
    assert validate_celebration_date("31.02") is None
    assert validate_celebration_date("32.01") is None
    print("OK dates")


def test_addresses() -> None:
    assert validate_delivery_address("ул. Преображенский Вал, д. 12, кв. 45")
    assert validate_delivery_address("преображенка") is None
    assert validate_delivery_address("20ук, ка") is None
    print("OK addresses")


def test_delivery_time() -> None:
    assert validate_delivery_time("08:00–12:00") == "08:00–12:00"
    assert validate_delivery_time("20ук, ка") is None
    assert validate_delivery_time("12:00-08:00") is None
    print("OK delivery time")


def test_phones() -> None:
    assert normalize_phone("+7 916 123-45-67") == "+79161234567"
    assert normalize_phone("89161234567") == "+79161234567"
    assert normalize_phone("123") is None
    print("OK phones")


if __name__ == "__main__":
    test_names()
    test_dates()
    test_addresses()
    test_delivery_time()
    test_phones()
    print("\nAll validation checks passed.")

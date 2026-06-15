from __future__ import annotations

import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

from config import MSK_TZ

DATE_PATTERN = re.compile(r"^(\d{1,2})[.\-/](\d{1,2})$")


def msk_today() -> date:
    return datetime.now(ZoneInfo(MSK_TZ)).date()


def normalize_date(raw: str) -> str | None:
    match = DATE_PATTERN.match(raw.strip())
    if not match:
        return None
    day, month = int(match.group(1)), int(match.group(2))
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    return f"{day:02d}-{month:02d}"


def parse_dd_mm(value: str) -> tuple[int, int]:
    day_str, month_str = value.split("-")
    return int(day_str), int(month_str)


def next_occurrence(dd_mm: str, reference: date | None = None) -> date:
    ref = reference or msk_today()
    day, month = parse_dd_mm(dd_mm)
    candidate = date(ref.year, month, day)
    if candidate < ref:
        candidate = date(ref.year + 1, month, day)
    return candidate


def days_until(dd_mm: str, reference: date | None = None) -> int:
    ref = reference or msk_today()
    return (next_occurrence(dd_mm, ref) - ref).days


def format_price(amount: int) -> str:
    return f"{amount:,} ₽".replace(",", " ")


def format_taboo_note(taboo_tags: str | None) -> str:
    if not taboo_tags:
        return ""
    items = [t.strip() for t in taboo_tags.split(",") if t.strip()]
    if not items:
        return ""
    joined = ", ".join(items)
    return f" (и мы исключили {joined})"

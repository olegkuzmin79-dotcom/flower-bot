from __future__ import annotations

import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

from config import MSK_TZ

DATE_PATTERN = re.compile(r"^(\d{1,2})[.\-/](\d{1,2})$")
NAME_PATTERN = re.compile(r"^[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё\s\-']{0,29}$")
VOWELS = set("аеёиоуыэюяaeiouyAEIOUYАЕЁИОУЫЭЮЯ")
ADDRESS_MARKERS = re.compile(
    r"(ул\.?|улиц[аеуы]?|пр\.?|проспект|пер\.?|переулок|бульвар|бул\.?|"
    r"шоссе|наб\.?|набережн|проезд|аллея|д\.|дом|кв\.?|квартира|корп\.?|строен|стр\.?)",
    re.IGNORECASE,
)
DELIVERY_TIME_PATTERN = re.compile(
    r"^(\d{1,2})[:.](\d{2})\s*[-–—]\s*(\d{1,2})[:.](\d{2})$"
)
PHONE_DIGITS_PATTERN = re.compile(r"\D")


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


def validate_celebration_date(raw: str) -> str | None:
    normalized = normalize_date(raw)
    if not normalized:
        return None
    day, month = parse_dd_mm(normalized)
    try:
        date(msk_today().year, month, day)
    except ValueError:
        return None
    return normalized


def _looks_like_gibberish(name: str) -> bool:
    letters = [c for c in name if c.isalpha()]
    if len(letters) < 3:
        return True
    if not any(c in VOWELS for c in letters):
        return True
    consonant_run = 0
    for char in name.lower():
        if not char.isalpha():
            continue
        if char in VOWELS:
            consonant_run = 0
        else:
            consonant_run += 1
            if consonant_run > 4:
                return True
    if re.search(r"(.)\1{2,}", name.lower()):
        return True
    return False


def validate_person_name(raw: str) -> str | None:
    name = " ".join((raw or "").split())
    if not NAME_PATTERN.match(name):
        return None
    letters = re.findall(r"[A-Za-zА-Яа-яЁё]", name)
    if len(letters) < 3:
        return None
    if re.search(r"\d", name):
        return None
    if _looks_like_gibberish(name):
        return None
    return name


def validate_delivery_address(raw: str) -> str | None:
    address = " ".join((raw or "").split())
    if len(address) < 15:
        return None
    if not ADDRESS_MARKERS.search(address):
        return None
    if not re.search(r"\d", address):
        return None
    if not re.search(r"[A-Za-zА-Яа-яЁё]{3,}", address):
        return None
    words = [w for w in re.split(r"[\s,]+", address) if w]
    if len(words) < 3:
        return None
    return address


def _valid_clock(hour: int, minute: int) -> bool:
    return 0 <= hour <= 23 and 0 <= minute <= 59


def validate_delivery_time(raw: str) -> str | None:
    text = " ".join((raw or "").split())
    match = DELIVERY_TIME_PATTERN.match(text)
    if not match:
        return None
    h1, m1, h2, m2 = (int(match.group(i)) for i in range(1, 5))
    if not (_valid_clock(h1, m1) and _valid_clock(h2, m2)):
        return None
    if (h1, m1) >= (h2, m2):
        return None
    return f"{h1:02d}:{m1:02d}–{h2:02d}:{m2:02d}"


def normalize_phone(raw: str) -> str | None:
    digits = PHONE_DIGITS_PATTERN.sub("", raw or "")
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if len(digits) == 10 and digits.startswith("9"):
        digits = "7" + digits
    if len(digits) == 11 and digits.startswith("7"):
        return f"+{digits}"
    return None


def format_phone(phone: str) -> str:
    digits = PHONE_DIGITS_PATTERN.sub("", phone)
    if len(digits) == 11:
        return f"+7 ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"
    return phone


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


from taboos import format_taboo_list


def format_taboo_note(taboo_tags: str | None) -> str:
    formatted = format_taboo_list(taboo_tags)
    if not formatted:
        return ""
    return f" (и мы исключили: {formatted})"

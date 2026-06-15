from __future__ import annotations

import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

from calendar import monthrange

from choices import MAX_APARTMENT, MAX_BUILDING, MAX_CUSTOMER_NAME, MAX_CUSTOM_TIME, MAX_STREET
from config import MSK_TZ

DATE_PATTERN = re.compile(r"^(\d{1,2})\.(\d{1,2})$")
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
CUSTOMER_NAME_PATTERN = re.compile(r"^[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё\-']{0,9}$")


def msk_today() -> date:
    return datetime.now(ZoneInfo(MSK_TZ)).date()


def normalize_date(raw: str) -> str | None:
    """ДД.ММ — только цифры и одна точка. День 1–31, месяц 1–12."""
    text = (raw or "").strip()
    match = DATE_PATTERN.match(text)
    if not match:
        return None
    day, month = int(match.group(1)), int(match.group(2))
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    return f"{day:02d}-{month:02d}"


def days_in_month(month: int, year: int | None = None) -> int:
    ref_year = year or msk_today().year
    return monthrange(ref_year, month)[1]


def build_celebration_date(day: int, month: int) -> str | None:
    if not (1 <= month <= 12 and 1 <= day <= days_in_month(month)):
        return None
    try:
        date(msk_today().year, month, day)
    except ValueError:
        return None
    return f"{day:02d}-{month:02d}"


def validate_celebration_date(raw: str) -> str | None:
    normalized = normalize_date(raw)
    if not normalized:
        return None
    day, month = parse_dd_mm(normalized)
    return build_celebration_date(day, month)


def validate_short_text(raw: str, *, max_len: int, min_len: int = 1) -> str | None:
    text = " ".join((raw or "").split())
    if not (min_len <= len(text) <= max_len):
        return None
    if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", text):
        return None
    return text


def validate_street_name(raw: str) -> str | None:
    street = validate_short_text(raw, max_len=MAX_STREET, min_len=3)
    if not street:
        return None
    if not re.search(r"[A-Za-zА-Яа-яЁё]{2,}", street):
        return None
    if re.fullmatch(r"\d+", street):
        return None
    return street


def validate_building(raw: str) -> str | None:
    building = validate_short_text(raw, max_len=MAX_BUILDING, min_len=1)
    if not building:
        return None
    if not re.search(r"\d", building):
        return None
    return building


def validate_apartment(raw: str | None) -> str | None:
    if raw is None:
        return None
    apt = (raw or "").strip()
    if not apt or not apt.isdigit() or len(apt) > MAX_APARTMENT:
        return None
    return apt


def validate_corps(raw: str | None) -> str | None:
    if not raw or not (raw or "").strip():
        return None
    return validate_building(raw)


def compose_delivery_address(
    district: str | None,
    street: str,
    building: str,
    apartment: str | None,
    corpus: str | None = None,
) -> str | None:
    street = validate_street_name(street or "")
    building = validate_building(building or "")
    if not street or not building:
        return None
    district = (district or "").strip()
    if district:
        parts = [f"{district}, ул. {street}, д. {building}"]
    else:
        parts = [f"Москва, ул. {street}, д. {building}"]
    if corpus:
        corp = validate_corps(corpus)
        if corp:
            parts.append(f"к. {corp}")
    if apartment:
        apt = validate_apartment(apartment)
        if not apt:
            return None
        parts.append(f"кв. {apt}")
    return ", ".join(parts)


def validate_order_comment(raw: str) -> str | None:
    from choices import MAX_ORDER_COMMENT

    text = " ".join((raw or "").split())
    if not text:
        return None
    return validate_short_text(text, max_len=MAX_ORDER_COMMENT, min_len=1)


def validate_delivery_time_custom(raw: str) -> str | None:
    text = validate_short_text(raw, max_len=MAX_CUSTOM_TIME, min_len=9)
    if not text:
        return None
    return validate_delivery_time(text)


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


def validate_custom_text(raw: str, max_len: int = 20) -> str | None:
    text = " ".join((raw or "").split())
    if not text or len(text) > max_len:
        return None
    if not NAME_PATTERN.match(text):
        return None
    if re.search(r"\d", text):
        return None
    return text


def validate_recipient_name(raw: str, max_len: int = 60) -> str | None:
  parts = (raw or "").split()
  if not parts or len(parts) > 3:
    return None
  normalized = []
  for part in parts:
    word = validate_person_name(part)
    if not word:
      return None
    normalized.append(word)
  name = " ".join(normalized)
  if len(name) > max_len:
    return None
  return name


def validate_full_fio(raw: str, max_len: int = 60) -> str | None:
    parts = (raw or "").split()
    if len(parts) != 3:
        return None
    normalized = []
    for part in parts:
        word = validate_person_name(part)
        if not word:
            return None
        normalized.append(word)
    fio = " ".join(normalized)
    if len(fio) > max_len:
        return None
    return fio


def validate_customer_name(raw: str) -> str | None:
    from choices import MAX_CUSTOMER_NAME

    return validate_full_fio(raw, max_len=MAX_CUSTOMER_NAME)


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


def validate_russian_mobile(raw: str) -> str | None:
    """Формат мобильного РФ (+79…). Реальность номера — только через SMS/звонок."""
    phone = normalize_phone(raw)
    if not phone:
        return None
    digits = phone[2:]
    if len(digits) != 10 or not digits.startswith("9"):
        return None
    return phone


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


def delivery_possible_this_year(dd_mm: str, reference: date | None = None) -> bool:
    """Есть ли ≥5 полных дней до ближайшей даты — успеем отправить букет в этом году."""
    from choices import MIN_DAYS_TO_MODIFY_CELEBRATION

    return days_until(dd_mm, reference) >= MIN_DAYS_TO_MODIFY_CELEBRATION


def delivery_warning_message(dd_mm: str, reference: date | None = None) -> str:
    from choices import MIN_DAYS_TO_MODIFY_CELEBRATION

    if delivery_possible_this_year(dd_mm, reference):
        return ""
    left = days_until(dd_mm, reference)
    if left == 0:
        return (
            "Праздник сегодня — букет на эту дату не отправим. "
            "Дата сохранена, напоминание придёт в следующем году."
        )
    return (
        f"До праздника {left} дн. (меньше {MIN_DAYS_TO_MODIFY_CELEBRATION}) — "
        "букет на эту дату не отправим. Дата сохранена на следующий год."
    )


def save_celebration_flash_message(celebration_date: str) -> str:
    if delivery_possible_this_year(celebration_date):
        return "Сохранено"
    return (
        "Сохранено. До праздника меньше 5 дней — букет на эту дату не отправим. "
        "Напоминание и заказ — в следующем году."
    )


# обратная совместимость для тестов
def can_modify_celebration(dd_mm: str, reference: date | None = None) -> bool:
    return delivery_possible_this_year(dd_mm, reference)


def modification_lock_message(dd_mm: str, reference: date | None = None) -> str:
    return delivery_warning_message(dd_mm, reference)


def format_celebration_date(dd_mm: str) -> str:
    day, month = parse_dd_mm(dd_mm)
    return f"{day:02d}.{month:02d}"


def format_reminder_details(celebration: dict) -> str:
    from bouquets import parse_style_list
    from config import STYLE_LABELS

    lines: list[str] = []
    role = celebration.get("recipient_role")
    fio = celebration.get("recipient_fio")
    if role and fio:
        who = celebration.get("recipient_role_custom") if role == "Свой вариант" else role
        lines.append(f"Кого поздравляем: {who}")
        lines.append(f"Имя: {fio}")
    else:
        lines.append(f"Кого поздравляем: {celebration.get('recipient_name', '')}")

    event_type = celebration.get("event_type")
    if event_type:
        if event_type == "other":
            event = celebration.get("event_custom") or "Другое событие"
        else:
            event = {"birthday": "День рождения", "march8": "8 марта"}.get(event_type, event_type)
        lines.append(f"Событие: {event}")

    lines.append(f"Дата: {format_celebration_date(celebration['celebration_date'])}")

    styles = parse_style_list(celebration.get("style_preference"))
    if len(styles) == len(STYLE_LABELS):
        lines.append("Стиль: любой")
    else:
        lines.append("Стиль: " + ", ".join(STYLE_LABELS[s] for s in styles))

    taboo = format_taboo_list(celebration.get("taboo_tags"))
    if taboo:
        lines.append(f"Ограничения: {taboo}")

    return "\n".join(lines)


def format_price(amount: int) -> str:
    return f"{amount:,} ₽".replace(",", " ")


from taboos import format_taboo_list


def format_taboo_note(taboo_tags: str | None) -> str:
    formatted = format_taboo_list(taboo_tags)
    if not formatted:
        return ""
    return f" (и мы исключили: {formatted})"

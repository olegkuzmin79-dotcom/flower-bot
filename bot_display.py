from __future__ import annotations

from typing import Any

from bouquets import parse_style_list
from choices import EVENT_TYPES, RECIPIENT_ROLE_CUSTOM, RECIPIENT_ROLES, STYLE_LABELS
from utils import days_until, format_celebration_date


def role_label(celebration: dict[str, Any]) -> str:
    role = celebration.get("recipient_role")
    if role:
        if role == RECIPIENT_ROLE_CUSTOM:
            return celebration.get("recipient_role_custom") or "Свой вариант"
        return role
    name = celebration.get("recipient_name") or ""
    for r in RECIPIENT_ROLES:
        if name.startswith(f"{r} "):
            return r
    return name.split(" · ")[0] if " · " in name else name


def event_label(celebration: dict[str, Any]) -> str:
    event_type = celebration.get("event_type")
    if not event_type:
        return ""
    if event_type == "other":
        return celebration.get("event_custom") or EVENT_TYPES["other"]
    return EVENT_TYPES.get(event_type, event_type)


def celebration_title(celebration: dict[str, Any]) -> str:
    fio = celebration.get("recipient_fio")
    who = role_label(celebration)
    if fio:
        return f"{who} · {fio}"
    return celebration.get("recipient_name") or who


def style_label_for(celebration: dict[str, Any]) -> str:
    pref = celebration.get("style_preference") or ""
    if not pref:
        return "Подберём сами"
    styles = parse_style_list(pref)
    if len(styles) >= len(STYLE_LABELS):
        return "Подберём сами"
    return ", ".join(STYLE_LABELS[s] for s in styles)


def format_celebration_line(celebration: dict[str, Any]) -> str:
    title = celebration_title(celebration)
    event = event_label(celebration)
    date = format_celebration_date(celebration["celebration_date"])
    days = days_until(celebration["celebration_date"])
    warn = " ⚠️ след. год" if days < 5 else ""
    style = style_label_for(celebration)
    event_part = f"{event}, " if event else ""
    return f"• {title} — {event_part}{date} (через {days} дн.){warn}\n  🎯 {style}"


def build_recipient_name(role: str, role_custom: str | None, fio: str) -> str:
    who = role_custom if role == RECIPIENT_ROLE_CUSTOM else role
    return f"{who} · {fio}"

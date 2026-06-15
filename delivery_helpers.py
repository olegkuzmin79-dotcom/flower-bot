from __future__ import annotations

from typing import Any

from choices import DELIVERY_TIME_SLOTS
from utils import parse_delivery_address


def celebration_has_saved_delivery(celebration: dict[str, Any]) -> bool:
    return bool(celebration.get("delivery_street") and celebration.get("delivery_building"))


def delivery_from_latest_order(order: dict[str, Any] | None) -> dict[str, Any] | None:
    if not order or not order.get("delivery_address"):
        return None
    parsed = parse_delivery_address(order["delivery_address"])
    if not parsed:
        return None
    return {
        "delivery_street": parsed["delivery_street"],
        "delivery_building": parsed["delivery_building"],
        "delivery_corps": parsed.get("delivery_corps"),
        "delivery_apartment": parsed.get("delivery_apartment"),
        "delivery_time": order.get("delivery_time") or "",
        "delivery_comment": order.get("delivery_comment") or "",
        "recipient_contact_phone": order.get("recipient_contact_phone") or "",
    }


def delivery_summary(defaults: dict[str, Any]) -> str:
    parts = [f"ул. {defaults['delivery_street']}, д. {defaults['delivery_building']}"]
    if defaults.get("delivery_corps"):
        parts.append(f"к. {defaults['delivery_corps']}")
    if defaults.get("delivery_apartment"):
        parts.append(f"кв. {defaults['delivery_apartment']}")
    if defaults.get("delivery_time"):
        parts.append(f"время {defaults['delivery_time']}")
    return ", ".join(parts)


def slot_or_custom(delivery_time: str) -> tuple[str, str]:
    if delivery_time in DELIVERY_TIME_SLOTS:
        return delivery_time, ""
    if delivery_time:
        return "other", delivery_time
    return "", ""

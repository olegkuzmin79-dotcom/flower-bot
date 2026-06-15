from __future__ import annotations

from choices import REFERRAL_BONUS_RUB, REFERRAL_START_PREFIX


def parse_referral_start(payload: str | None) -> int | None:
    if not payload or not payload.startswith(REFERRAL_START_PREFIX):
        return None
    raw = payload[len(REFERRAL_START_PREFIX) :]
    if not raw.isdigit():
        return None
    referrer_id = int(raw)
    return referrer_id if referrer_id > 0 else None


def order_charge_amount(budget_selected: int, discount_applied: int | None) -> int:
    discount = max(0, int(discount_applied or 0))
    return max(0, int(budget_selected) - discount)


def referral_link(bot_username: str, user_id: int) -> str:
    username = bot_username.lstrip("@")
    return f"https://t.me/{username}?start={REFERRAL_START_PREFIX}{user_id}"

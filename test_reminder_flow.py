"""Local checks for 5-day reminder flow (no Telegram needed). Run: py test_reminder_flow.py"""
from __future__ import annotations

from datetime import date, timedelta

from bouquets import BOUQUETS, filter_bouquets
from config import BUDGETS, REMINDER_DAYS_BEFORE
from utils import days_until, format_price, msk_today, normalize_date


def test_catalog() -> None:
    assert len(BOUQUETS) == 9
    for bouquet in BOUQUETS:
        assert bouquet.budget in BUDGETS.values()
        assert bouquet.caption()
        assert format_price(bouquet.budget) in bouquet.caption()
    print("OK catalog: 9 bouquets with prices in captions")


def test_filter_by_style() -> None:
    for style in ("classic", "tender", "bright"):
        items = filter_bouquets(style)
        assert len(items) == 3
        budgets = sorted(b.budget for b in items)
        assert budgets == sorted(BUDGETS.values())
    print("OK filter: 3 bouquets per style with all budget tiers")


def test_taboo_filter() -> None:
    without_lilies = filter_bouquets("tender", "лилии")
    assert len(without_lilies) == 3
    print("OK taboo filter")


def test_reminder_timing() -> None:
    today = msk_today()
    target = today + timedelta(days=REMINDER_DAYS_BEFORE)
    dd_mm = f"{target.day:02d}-{target.month:02d}"
    assert days_until(dd_mm, today) == REMINDER_DAYS_BEFORE
    print(f"OK timing: celebration on {dd_mm} triggers reminder today ({today})")


def test_date_normalization() -> None:
    assert normalize_date("25.10") == "25-10"
    assert normalize_date("8-3") == "08-03"
    print("OK date normalization")


def demo_reminder_text() -> None:
    celebration = {
        "recipient_name": "Жена Катя",
        "celebration_date": "25-10",
        "style_preference": "tender",
        "taboo_tags": "лилии",
    }
    bouquets = filter_bouquets(celebration["style_preference"], celebration["taboo_tags"])[:3]
    print("\n--- Demo reminder (5 days before) ---")
    print(f"To: user about {celebration['recipient_name']} on {celebration['celebration_date']}")
    print("Album:")
    for index, bouquet in enumerate(bouquets, start=1):
        print(f"  Photo {index}: {bouquet.caption().replace(chr(10), ' | ')}")
    print("Budget buttons:")
    for key, amount in BUDGETS.items():
        print(f"  {key}: {format_price(amount)}")


if __name__ == "__main__":
    test_catalog()
    test_filter_by_style()
    test_taboo_filter()
    test_reminder_timing()
    test_date_normalization()
    demo_reminder_text()
    print("\nAll checks passed.")

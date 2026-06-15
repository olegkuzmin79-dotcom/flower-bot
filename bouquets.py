from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from config import ASSETS_DIR, BUDGETS, BUDGET_LABELS, STYLE_LABELS
from choices import BUDGET_EFFECT_LABELS, REMINDER_PACKAGING_NOTE


@dataclass(frozen=True)
class Bouquet:
    id: int
    name: str
    style: str
    budget: int
    tags: tuple[str, ...]
    description: str
    image_url: str

    def image_source(self) -> str | Path:
        local = ASSETS_DIR / f"bouquet_{self.id}.jpg"
        if local.exists():
            return local
        return self.image_url

    def caption(self) -> str:
        budget_label = BUDGET_LABELS.get(self.budget, "")
        effect = BUDGET_EFFECT_LABELS.get(self.budget, self.description)
        return f"{budget_label}\n{effect}\n💰 {self.budget:,} ₽".replace(",", " ")

    def user_effect(self) -> str:
        return BUDGET_EFFECT_LABELS.get(self.budget, self.description)


def _build_catalog() -> list[Bouquet]:
    styles = ("classic", "tender", "bright")
    style_names = {
        "classic": "Классика",
        "tender": "Нежность",
        "bright": "Яркий",
    }
    budget_keys = ("econom", "business", "premium")
    budget_labels = {"econom": "Эконом", "business": "Бизнес", "premium": "Премиум"}
    tag_map = {
        ("classic", "econom"): ("классика", "розы", "эвкалипт"),
        ("classic", "business"): ("классика", "розы", "зелень"),
        ("classic", "premium"): ("классика", "розы"),
        ("tender", "econom"): ("нежный", "пастель", "розы", "гипсофила"),
        ("tender", "business"): ("нежный", "пастель", "розы", "эустома"),
        ("tender", "premium"): ("нежный", "пастель", "пионы", "розы", "орхидеи"),
        ("bright", "econom"): ("яркий", "герберы", "хризантемы"),
        ("bright", "business"): ("яркий", "экзотика", "герберы", "тюльпаны"),
        ("bright", "premium"): ("яркий", "экзотика", "тюльпаны", "орхидеи"),
    }
    description_map = {
        ("classic", "econom"): "15 красных роз, эвкалипт",
        ("classic", "business"): "25 роз премиум, зелень, упаковка",
        ("classic", "premium"): "51 роза, ленты, премиум-упаковка",
        ("tender", "econom"): "Пионовидные розы, гипсофила",
        ("tender", "business"): "Розы, эустома, пастельная гамма",
        ("tender", "premium"): "Пионы, розы, орхидея, шёлковые ленты",
        ("bright", "econom"): "Герберы, хризантемы, яркая лента",
        ("bright", "business"): "Экзотический микс, тропические акценты",
        ("bright", "premium"): "Авторский яркий букет, редкие сорта",
    }

    catalog: list[Bouquet] = []
    bouquet_id = 1
    for style in styles:
        for budget_key in budget_keys:
            budget = BUDGETS[budget_key]
            catalog.append(
                Bouquet(
                    id=bouquet_id,
                    name=f"{style_names[style]} — {budget_labels[budget_key]}",
                    style=style,
                    budget=budget,
                    tags=tag_map[(style, budget_key)],
                    description=description_map[(style, budget_key)],
                    image_url=f"https://picsum.photos/seed/flower-{bouquet_id}/800/600",
                )
            )
            bouquet_id += 1
    return catalog


BOUQUETS: list[Bouquet] = _build_catalog()

STYLE_ORDER = ("classic", "tender", "bright")
STYLE_NAMES = STYLE_LABELS
BUSINESS_BUDGET = BUDGETS["business"]
AMOUNT_TO_BUDGET_KEY = {amount: key for key, amount in BUDGETS.items()}
PACKAGING_NOTE = REMINDER_PACKAGING_NOTE


def style_image_source(style: str) -> str | Path:
    bouquet = business_bouquet(style)
    if bouquet:
        return bouquet.image_source()
    return BOUQUETS[0].image_source()


def reminder_options_caption(bouquets: list[Bouquet], style_label: str) -> str:
    lines = [f"Стиль: {style_label}"]
    for bouquet in bouquets:
        budget_label = BUDGET_LABELS.get(bouquet.budget, "")
        price = f"{bouquet.budget:,} ₽".replace(",", " ")
        lines.append(f"• {budget_label} — {bouquet.description} ({price})")
    return "\n".join(lines)


def filter_bouquets(
    style: str,
    taboo_tags: str | None = None,
    budget: int | None = None,
) -> list[Bouquet]:
    taboo = {t.strip().lower() for t in (taboo_tags or "").split(",") if t.strip()}
    result: list[Bouquet] = []
    for bouquet in BOUQUETS:
        if bouquet.style != style:
            continue
        if budget is not None and bouquet.budget != budget:
            continue
        if taboo and taboo.intersection(bouquet.tags):
            continue
        result.append(bouquet)
    return result


def parse_style_list(style_preference: str | None) -> list[str]:
    if not style_preference:
        return list(STYLE_ORDER)
    parts = [s.strip() for s in style_preference.split(",") if s.strip()]
    valid = [s for s in parts if s in STYLE_NAMES]
    return valid or list(STYLE_ORDER)


def explicit_styles(style_preference: str | None) -> list[str]:
    if not style_preference:
        return []
    parts = [s.strip() for s in style_preference.split(",") if s.strip()]
    return [s for s in parts if s in STYLE_NAMES]


def bouquets_for_style(style: str, taboo_tags: str | None = None) -> list[Bouquet]:
    return sorted(filter_bouquets(style, taboo_tags), key=lambda b: b.budget)


def business_bouquet(style: str, taboo_tags: str | None = None) -> Bouquet | None:
    matches = filter_bouquets(style, taboo_tags, BUSINESS_BUDGET)
    if matches:
        return matches[0]
    fallback = filter_bouquets(style, None, BUSINESS_BUDGET)
    return fallback[0] if fallback else None


@dataclass(frozen=True)
class ReminderStyleCard:
    style_key: str
    style_label: str
    hero: Bouquet
    tiers: tuple[Bouquet, ...]


@dataclass(frozen=True)
class ReminderDisplay:
    mode: str
    packaging_note: str
    photos: tuple[Bouquet, ...]
    cards: tuple[ReminderStyleCard, ...]
    single_style_key: str | None = None


def build_reminder_display(style_preference: str | None, taboo_tags: str | None = None) -> ReminderDisplay:
    explicit = explicit_styles(style_preference)
    if len(explicit) == 1:
        style = explicit[0]
        tiers = bouquets_for_style(style, taboo_tags) or bouquets_for_style(style, None)
        return ReminderDisplay(
            mode="budget_photos",
            packaging_note=PACKAGING_NOTE,
            photos=tuple(tiers[:3]),
            cards=(),
            single_style_key=style,
        )

    cards: list[ReminderStyleCard] = []
    for style in parse_style_list(style_preference):
        hero = business_bouquet(style, taboo_tags)
        if not hero:
            continue
        tiers = bouquets_for_style(style, taboo_tags) or bouquets_for_style(style, None)
        cards.append(
            ReminderStyleCard(
                style_key=style,
                style_label=STYLE_NAMES[style],
                hero=hero,
                tiers=tuple(tiers[:3]),
            )
        )
    return ReminderDisplay(
        mode="style_heroes",
        packaging_note=PACKAGING_NOTE,
        photos=(),
        cards=tuple(cards),
    )


def filter_bouquets_for_celebration(
    style_preference: str | None,
    taboo_tags: str | None = None,
    budget: int | None = None,
    limit: int = 3,
) -> list[Bouquet]:
    seen: set[int] = set()
    result: list[Bouquet] = []
    for style in parse_style_list(style_preference):
        for bouquet in filter_bouquets(style, taboo_tags, budget):
            if bouquet.id in seen:
                continue
            seen.add(bouquet.id)
            result.append(bouquet)
            if len(result) >= limit:
                return result
    return result


def pick_bouquet_for_order(style: str, budget: int, taboo_tags: str | None) -> Bouquet | None:
    matches = filter_bouquets(style, taboo_tags, budget)
    return matches[0] if matches else None

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from config import ASSETS_DIR, BUDGETS, BUDGET_LABELS


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
        return f"{self.name}\n{self.description}\n💰 {budget_label} — {self.budget:,} ₽".replace(",", " ")


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
        "classic": ("классика", "розы"),
        "tender": ("нежный", "пастель"),
        "bright": ("яркий", "экзотика"),
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
                    tags=tag_map[style],
                    description=description_map[(style, budget_key)],
                    image_url=f"https://picsum.photos/seed/flower-{bouquet_id}/800/600",
                )
            )
            bouquet_id += 1
    return catalog


BOUQUETS: list[Bouquet] = _build_catalog()

STYLE_HERO_BOUQUET_ID = {"classic": 1, "tender": 4, "bright": 7}


def style_image_source(style: str) -> str | Path:
    hero_id = STYLE_HERO_BOUQUET_ID.get(style, 1)
    local = ASSETS_DIR / f"bouquet_{hero_id}.jpg"
    if local.exists():
        return local
    return BOUQUETS[hero_id - 1].image_url if hero_id <= len(BOUQUETS) else BOUQUETS[0].image_url


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


def pick_bouquet_for_order(style: str, budget: int, taboo_tags: str | None) -> Bouquet | None:
    matches = filter_bouquets(style, taboo_tags, budget)
    return matches[0] if matches else None

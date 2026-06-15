"""Ограничения по цветам — мультивыбор при онбординге."""

TABOO_OPTIONS: tuple[tuple[str, str], ...] = (
    ("желтый", "Жёлтые цветы"),
    ("лилии", "Лилии"),
    ("хризантемы", "Хризантемы"),
    ("гипсофила", "Гипсофила"),
    ("розы", "Розы"),
    ("тюльпаны", "Тюльпаны"),
    ("орхидеи", "Орхидеи"),
    ("пионы", "Пионы"),
    ("герберы", "Герберы"),
)


def taboo_label(key: str) -> str:
    for tag, label in TABOO_OPTIONS:
        if tag == key:
            return label
    return key


def format_taboo_list(taboo_tags: str | None) -> str:
    if not taboo_tags:
        return ""
    keys = [t.strip() for t in taboo_tags.split(",") if t.strip()]
    if not keys:
        return ""
    return ", ".join(taboo_label(k) for k in keys)

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from choices import (
    DELIVERY_TIME_SLOTS,
    EVENT_TYPES,
    RECIPIENT_ROLE_CUSTOM,
    RECIPIENT_ROLES,
    ROLE_BUTTON_LABELS,
    STYLE_BUTTON_LABELS,
)
from config import BUDGETS
from taboos import TABOO_OPTIONS


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Добавить праздник")],
            [KeyboardButton(text="📅 Мои праздники"), KeyboardButton(text="🔔 Тест подборки")],
            [KeyboardButton(text="🤝 Спасти друга")],
        ],
        resize_keyboard=True,
    )


def recipient_keyboard() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for role in RECIPIENT_ROLES:
        label = ROLE_BUTTON_LABELS.get(role, role)
        row.append(InlineKeyboardButton(text=label, callback_data=f"recipient:{role}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append(
        [InlineKeyboardButton(text=RECIPIENT_ROLE_CUSTOM, callback_data=f"recipient:{RECIPIENT_ROLE_CUSTOM}")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def event_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=EVENT_TYPES["birthday"], callback_data="event:birthday")],
            [InlineKeyboardButton(text=EVENT_TYPES["march8"], callback_data="event:march8")],
            [InlineKeyboardButton(text=EVENT_TYPES["feb14"], callback_data="event:feb14")],
            [InlineKeyboardButton(text=EVENT_TYPES["wedding"], callback_data="event:wedding")],
            [InlineKeyboardButton(text=EVENT_TYPES["banquet"], callback_data="event:banquet")],
            [InlineKeyboardButton(text=EVENT_TYPES["other"], callback_data="event:other")],
        ]
    )


def style_keyboard(selected: set[str] | None = None) -> InlineKeyboardMarkup:
    chosen = selected or set()
    rows: list[list[InlineKeyboardButton]] = []
    for key, label in STYLE_BUTTON_LABELS.items():
        prefix = "✅ " if key in chosen else ""
        rows.append(
            [InlineKeyboardButton(text=f"{prefix}{label}", callback_data=f"style:toggle:{key}")]
        )
    rows.append([InlineKeyboardButton(text="Подберём сами", callback_data="style:any")])
    rows.append([InlineKeyboardButton(text="✔️ Готово", callback_data="style:done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def taboo_keyboard(selected: set[str] | None = None) -> InlineKeyboardMarkup:
    chosen = selected or set()
    rows: list[list[InlineKeyboardButton]] = []
    for tag, label in TABOO_OPTIONS:
        prefix = "✅ " if tag in chosen else ""
        rows.append(
            [InlineKeyboardButton(text=f"{prefix}{label}", callback_data=f"taboo:toggle:{tag}")]
        )
    rows.append([InlineKeyboardButton(text="Без ограничений", callback_data="taboo:clear")])
    rows.append([InlineKeyboardButton(text="✔️ Готово", callback_data="taboo:done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def apartment_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Без квартиры", callback_data="apt:none")],
            [InlineKeyboardButton(text="✏️ Указать квартиру", callback_data="apt:custom")],
        ]
    )


def delivery_time_keyboard() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for slot in DELIVERY_TIME_SLOTS:
        rows.append([InlineKeyboardButton(text=slot, callback_data=f"dtime:{slot}")])
    rows.append([InlineKeyboardButton(text="✏️ Ваш вариант", callback_data="dtime:other")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def delivery_reuse_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Как в прошлый раз", callback_data="dlv:reuse")],
            [InlineKeyboardButton(text="✏️ Другой адрес", callback_data="dlv:new")],
        ]
    )


def comment_skip_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Пропустить", callback_data="cmt:skip")]]
    )


def recipient_phone_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📱 Тот же, что у заказчика", callback_data="rcpt:same")],
        ]
    )


def budget_keyboard(celebration_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"🟢 Эконом — {BUDGETS['econom']:,} ₽".replace(",", " "),
                    callback_data=f"budget:econom:{celebration_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"🔵 Бизнес — {BUDGETS['business']:,} ₽".replace(",", " "),
                    callback_data=f"budget:business:{celebration_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"🟣 Премиум — {BUDGETS['premium']:,} ₽".replace(",", " "),
                    callback_data=f"budget:premium:{celebration_id}",
                )
            ],
        ]
    )


def celebrations_edit_keyboard(items: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for cid, title in items[:6]:
        label = title if len(title) <= 28 else title[:25] + "…"
        rows.append([InlineKeyboardButton(text=f"✏️ {label}", callback_data=f"edcel:{cid}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def celebration_edit_menu_keyboard(celebration_id: int) -> InlineKeyboardMarkup:
    cid = celebration_id
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👤 Кого поздравляем", callback_data=f"efld:{cid}:role")],
            [InlineKeyboardButton(text="📝 Имя", callback_data=f"efld:{cid}:name")],
            [InlineKeyboardButton(text="🎉 С чем поздравляем", callback_data=f"efld:{cid}:event")],
            [InlineKeyboardButton(text="📅 Дата", callback_data=f"efld:{cid}:date")],
            [InlineKeyboardButton(text="💐 Эффект", callback_data=f"efld:{cid}:style")],
            [InlineKeyboardButton(text="⛔ Ограничения", callback_data=f"efld:{cid}:taboo")],
            [InlineKeyboardButton(text="🗑 Удалить событие", callback_data=f"efld:{cid}:delete")],
        ]
    )


def phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Отправить телефон", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def test_pay_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Тестовая оплата",
                    callback_data=f"pay:test:{order_id}",
                )
            ]
        ]
    )

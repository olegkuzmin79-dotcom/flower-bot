from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from config import BUDGETS
from taboos import TABOO_OPTIONS


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Добавить праздник")],
            [KeyboardButton(text="📅 Мои праздники"), KeyboardButton(text="🔔 Тест подборки")],
        ],
        resize_keyboard=True,
    )


def recipient_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Жена", callback_data="recipient:Жена"),
                InlineKeyboardButton(text="Мама", callback_data="recipient:Мама"),
            ],
            [
                InlineKeyboardButton(text="Девушка", callback_data="recipient:Девушка"),
                InlineKeyboardButton(text="Другое", callback_data="recipient:Другое"),
            ],
        ]
    )


def style_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Классика", callback_data="style:classic")],
            [InlineKeyboardButton(text="Нежность", callback_data="style:tender")],
            [InlineKeyboardButton(text="Яркий", callback_data="style:bright")],
        ]
    )


def taboo_keyboard(selected: set[str] | None = None) -> InlineKeyboardMarkup:
    chosen = selected or set()
    rows: list[list[InlineKeyboardButton]] = []
    for tag, label in TABOO_OPTIONS:
        prefix = "✅ " if tag in chosen else ""
        rows.append(
            [InlineKeyboardButton(text=f"{prefix}{label}", callback_data=f"taboo:toggle:{tag}")]
        )
    rows.append([InlineKeyboardButton(text="✔️ Готово", callback_data="taboo:done")])
    rows.append([InlineKeyboardButton(text="Без ограничений", callback_data="taboo:clear")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


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

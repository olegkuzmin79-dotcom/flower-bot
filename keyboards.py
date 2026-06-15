from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from config import BUDGETS


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


def taboo_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Нет", callback_data="taboo:none")],
            [InlineKeyboardButton(text="Не любит желтый", callback_data="taboo:желтый")],
            [InlineKeyboardButton(text="Не любит лилии", callback_data="taboo:лилии")],
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

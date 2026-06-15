from __future__ import annotations

import logging
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, Message

from bouquets import filter_bouquets, reminder_options_caption, style_image_source
from config import ADMIN_CHAT_ID, BUDGETS, BUDGET_LABELS, STYLE_LABELS
from database import (
    add_celebration,
    create_order,
    get_celebration,
    get_order,
    get_user_celebrations,
    update_order_delivery,
    update_order_payment,
    upsert_user,
)
from keyboards import (
    budget_keyboard,
    main_menu_keyboard,
    recipient_keyboard,
    style_keyboard,
    taboo_keyboard,
    test_pay_keyboard,
)
from payments import create_payment
from utils import format_price, format_taboo_note, normalize_date

logger = logging.getLogger(__name__)
router = Router()


class AddCelebration(StatesGroup):
    recipient_role = State()
    recipient_name = State()
    celebration_date = State()
    style_preference = State()
    taboo_tags = State()


class Checkout(StatesGroup):
    delivery_address = State()
    delivery_time = State()


WELCOME_TEXT = (
    "Привет! Я твой личный ассистент по информационной безопасности отношений. "
    "Помогу никогда не забыть про важные даты и отправить идеальные цветы в 1 клик."
)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await upsert_user(message.from_user.id, message.from_user.username)
    await message.answer(WELCOME_TEXT, reply_markup=main_menu_keyboard())
    await message.answer("Начни с добавления первого праздника 👇")


@router.message(F.text == "➕ Добавить праздник")
async def add_celebration_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AddCelebration.recipient_role)
    await message.answer("Кто получательница?", reply_markup=recipient_keyboard())


@router.callback_query(F.data.startswith("recipient:"))
async def process_recipient(callback: CallbackQuery, state: FSMContext) -> None:
    role = callback.data.split(":", 1)[1]
    await state.update_data(recipient_role=role)
    await state.set_state(AddCelebration.recipient_name)
    await callback.message.edit_text(f"Как её зовут? (например: Катя)")
    await callback.answer()


@router.message(AddCelebration.recipient_name)
async def process_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer("Введи имя получательницы (минимум 2 символа).")
        return
    data = await state.get_data()
    full_name = f"{data['recipient_role']} {name}"
    await state.update_data(recipient_name=full_name)
    await state.set_state(AddCelebration.celebration_date)
    await message.answer("Какая дата события? Формат: 25.10")


@router.message(AddCelebration.celebration_date)
async def process_date(message: Message, state: FSMContext) -> None:
    normalized = normalize_date(message.text or "")
    if not normalized:
        await message.answer("Не понял дату. Пример: 25.10 или 08-03")
        return
    await state.update_data(celebration_date=normalized)
    await state.set_state(AddCelebration.style_preference)
    await message.answer("Какой стиль цветов она предпочитает?", reply_markup=style_keyboard())


@router.callback_query(F.data.startswith("style:"), AddCelebration.style_preference)
async def process_style(callback: CallbackQuery, state: FSMContext) -> None:
    style = callback.data.split(":", 1)[1]
    await state.update_data(style_preference=style)
    await state.set_state(AddCelebration.taboo_tags)
    await callback.message.edit_text("Есть ли табу или аллергия?", reply_markup=taboo_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("taboo:"), AddCelebration.taboo_tags)
async def process_taboo(callback: CallbackQuery, state: FSMContext) -> None:
    taboo_raw = callback.data.split(":", 1)[1]
    taboo_tags = None if taboo_raw == "none" else taboo_raw
    data = await state.get_data()
    celebration_id = await add_celebration(
        user_id=callback.from_user.id,
        recipient_name=data["recipient_name"],
        celebration_date=data["celebration_date"],
        style_preference=data["style_preference"],
        taboo_tags=taboo_tags,
    )
    await state.clear()
    style_label = STYLE_LABELS.get(data["style_preference"], data["style_preference"])
    await callback.message.edit_text(
        "Готово! Праздник сохранён ✅\n\n"
        f"👤 {data['recipient_name']}\n"
        f"📅 {data['celebration_date']}\n"
        f"🌸 Стиль: {style_label}\n\n"
        "За 5 дней до даты пришлю подборку букетов и кнопки оплаты в 1 клик."
    )
    await callback.answer()
    logger.info("Celebration %s created for user %s", celebration_id, callback.from_user.id)


@router.message(F.text == "📅 Мои праздники")
async def list_celebrations(message: Message) -> None:
    items = await get_user_celebrations(message.from_user.id)
    if not items:
        await message.answer("Пока нет сохранённых праздников. Нажми «➕ Добавить праздник».")
        return
    lines = ["📅 Твои праздники:\n"]
    for item in items:
        style = STYLE_LABELS.get(item["style_preference"], item["style_preference"])
        taboo = f"\n   ⛔ табу: {item['taboo_tags']}" if item.get("taboo_tags") else ""
        lines.append(f"• {item['recipient_name']} — {item['celebration_date']} ({style}){taboo}")
    await message.answer("\n".join(lines))


async def _send_test_reminder(message: Message, bot: Bot) -> None:
    items = await get_user_celebrations(message.from_user.id)
    if not items:
        await message.answer(
            "Сначала добавь праздник через «➕ Добавить праздник», "
            "потом нажми «🔔 Тест подборки»."
        )
        return

    celebration = {**items[-1], "user_id": message.from_user.id}
    style_label = STYLE_LABELS.get(celebration["style_preference"], celebration["style_preference"])
    await message.answer(
        "🧪 Демо: так выглядит напоминание за 5 дней до праздника.\n"
        f"Праздник: {celebration['recipient_name']} ({celebration['celebration_date']}), "
        f"стиль — {style_label}."
    )
    await send_reminder(bot, celebration)


@router.message(F.text == "🔔 Тест подборки")
async def test_reminder_button(message: Message, bot: Bot) -> None:
    await _send_test_reminder(message, bot)


@router.message(Command("test_reminder"))
async def test_reminder_command(message: Message, bot: Bot) -> None:
    await _send_test_reminder(message, bot)


@router.callback_query(F.data.startswith("budget:"))
async def select_budget(callback: CallbackQuery, state: FSMContext) -> None:
    _, budget_key, celebration_id_str = callback.data.split(":")
    celebration_id = int(celebration_id_str)
    celebration = await get_celebration(celebration_id)
    if not celebration or celebration["user_id"] != callback.from_user.id:
        await callback.answer("Праздник не найден.", show_alert=True)
        return

    amount = BUDGETS[budget_key]
    order_id = await create_order(callback.from_user.id, celebration_id, amount)
    await state.set_state(Checkout.delivery_address)
    await state.update_data(order_id=order_id, celebration_id=celebration_id)
    await callback.message.answer(
        f"Отличный выбор — {BUDGET_LABELS[amount]} ({amount:,} ₽).\n"
        "Укажи точный адрес доставки в Москве:".replace(",", " ")
    )
    await callback.answer()


@router.message(Checkout.delivery_address)
async def process_address(message: Message, state: FSMContext) -> None:
    address = (message.text or "").strip()
    if len(address) < 5:
        await message.answer("Укажи полный адрес доставки в Москве.")
        return
    await state.update_data(delivery_address=address)
    await state.set_state(Checkout.delivery_time)
    await message.answer("Укажи удобный интервал доставки (например: 25.10, 08:00–12:00).")


@router.message(Checkout.delivery_time)
async def process_delivery_time(message: Message, state: FSMContext, bot: Bot) -> None:
    delivery_time = (message.text or "").strip()
    if len(delivery_time) < 3:
        await message.answer("Укажи интервал доставки.")
        return

    data = await state.get_data()
    order_id = data["order_id"]
    celebration_id = data["celebration_id"]
    delivery_address = data["delivery_address"]

    await update_order_delivery(order_id, delivery_address, delivery_time)
    order = await get_order(order_id)
    celebration = await get_celebration(celebration_id)
    if not order or not celebration:
        await message.answer("Не удалось найти заказ. Начни заново из напоминания.")
        await state.clear()
        return

    amount = order["budget_selected"]
    description = f"Букет для {celebration['recipient_name']} — заказ #{order_id}"

    try:
        payment = await create_payment(
            amount_rub=amount,
            description=description,
            return_url="https://t.me/",
            metadata={"order_id": order_id, "user_id": message.from_user.id},
        )
        await update_order_payment(order_id, "pending", payment["id"])
    except Exception:
        logger.exception("Payment creation failed for order %s", order_id)
        await message.answer("Не удалось создать платёж. Попробуй позже или напиши поддержке.")
        await state.clear()
        return

    await state.clear()

    if payment.get("test_mode"):
        await message.answer(
            f"Заказ #{order_id} оформлен.\n"
            f"Сумма: {amount:,} ₽\n"
            f"Адрес: {delivery_address}\n"
            f"Время: {delivery_time}\n\n"
            "Тестовый режим: нажми кнопку ниже для имитации оплаты.".replace(",", " "),
            reply_markup=test_pay_keyboard(order_id),
        )
        return

    await message.answer(
        f"Заказ #{order_id} оформлен.\n"
        f"Оплати по ссылке:\n{payment['confirmation_url']}"
    )


@router.callback_query(F.data.startswith("pay:test:"))
async def test_payment(callback: CallbackQuery, bot: Bot) -> None:
    order_id = int(callback.data.split(":")[2])
    order = await get_order(order_id)
    if not order or order["user_id"] != callback.from_user.id:
        await callback.answer("Заказ не найден.", show_alert=True)
        return

    await update_order_payment(order_id, "paid", order.get("yookassa_payment_id"))
    celebration = await get_celebration(order["celebration_id"])
    if not celebration:
        await callback.answer("Ошибка данных заказа.", show_alert=True)
        return

    style_label = STYLE_LABELS.get(celebration["style_preference"], celebration["style_preference"])
    budget_label = BUDGET_LABELS.get(order["budget_selected"], str(order["budget_selected"]))

    await callback.message.edit_text(
        f"✅ Оплата прошла успешно!\n"
        f"Заказ #{order_id} принят в работу.\n"
        f"Доставка: {order['delivery_address']}, {order['delivery_time']}"
    )
    await callback.answer("Оплачено")

    await send_florist_task(bot, order_id, style_label, budget_label, celebration["celebration_date"])
    logger.info("Order %s paid (test) for user %s", order_id, callback.from_user.id)


async def send_florist_task(
    bot: Bot,
    order_id: int,
    style_label: str,
    budget_label: str,
    celebration_date: str,
) -> None:
    if not ADMIN_CHAT_ID:
        logger.warning("FLORIST_CHAT_ID not set — florist task for order %s skipped", order_id)
        return
    text = (
        f"Заказ №{order_id}. Сборка букета из категории {style_label} ({budget_label}). "
        f"Готовность: {celebration_date} к 08:00"
    )
    try:
        await bot.send_message(int(ADMIN_CHAT_ID), text)
    except Exception:
        logger.exception("Failed to send florist task for order %s", order_id)


def _photo_input(source: str | Path) -> FSInputFile | str:
    if isinstance(source, Path):
        return FSInputFile(source)
    return source


async def send_reminder(bot: Bot, celebration: dict) -> None:
    user_id = celebration["user_id"]
    style = celebration["style_preference"]
    taboo = celebration.get("taboo_tags")
    bouquets = filter_bouquets(style, taboo)[:3]
    if not bouquets:
        bouquets = filter_bouquets(style)[:3]

    style_label = STYLE_LABELS.get(style, style)
    taboo_note = format_taboo_note(taboo)
    price_lines = "\n".join(
        f"  {index}. {bouquet.name} — {format_price(bouquet.budget)}"
        for index, bouquet in enumerate(bouquets, start=1)
    )
    photo_caption = reminder_options_caption(bouquets, style_label)
    text = (
        f"🚨 Привет! Через 5 дней день рождения у: {celebration['recipient_name']} "
        f"({celebration['celebration_date']}).\n\n"
        f"Мы помним, что она любит {style_label.lower()} тона{taboo_note}.\n\n"
        "Фото выше — пример стиля. Три варианта отличаются размером и составом:\n\n"
        f"💐 Варианты и цены:\n{price_lines}\n\n"
        "Выбери бюджет кнопкой ниже:"
    )

    try:
        await bot.send_photo(
            user_id,
            photo=_photo_input(style_image_source(style)),
            caption=photo_caption,
        )
        await bot.send_message(
            user_id,
            text,
            reply_markup=budget_keyboard(celebration["id"]),
        )
    except Exception:
        logger.exception("Failed to send reminder to user %s", user_id)


async def send_payment_nudge(bot: Bot, celebration: dict, order: dict) -> None:
    user_id = celebration["user_id"]
    amount = order["budget_selected"]
    text = (
        f"⏰ Через 3 дня — {celebration['recipient_name']} ({celebration['celebration_date']}).\n"
        f"Заказ #{order['order_id']} на {amount:,} ₽ ещё не оплачен.\n"
        "Заверши оплату, чтобы мы успели собрать букет.".replace(",", " ")
    )
    try:
        if order.get("yookassa_payment_id", "").startswith("test_"):
            await bot.send_message(user_id, text, reply_markup=test_pay_keyboard(order["order_id"]))
        else:
            await bot.send_message(user_id, text)
    except Exception:
        logger.exception("Failed to send payment nudge to user %s", user_id)

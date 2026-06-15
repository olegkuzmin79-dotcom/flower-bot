from __future__ import annotations

import logging
import re
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, InputMediaPhoto, Message

from choices import MAX_APARTMENT, MAX_BUILDING, MAX_CUSTOMER_NAME, MAX_RECIPIENT_NAME, MAX_STREET
from bouquets import build_reminder_display
from config import ADMIN_CHAT_ID, BUDGETS, BUDGET_LABELS, STYLE_LABELS
from database import (
    add_celebration,
    create_order,
    get_celebration,
    get_order,
    get_user,
    get_user_celebrations,
    update_order_delivery,
    update_order_payment,
    update_user_profile,
    upsert_user,
)
from keyboards import (
    apartment_keyboard,
    budget_keyboard,
    delivery_time_keyboard,
    district_keyboard,
    main_menu_keyboard,
    phone_keyboard,
    recipient_keyboard,
    recipient_name_keyboard,
    style_keyboard,
    taboo_keyboard,
    test_pay_keyboard,
)
from payments import create_payment
from taboos import format_taboo_list
from utils import (
    compose_delivery_address,
    format_phone,
    format_celebration_date,
    format_price,
    format_reminder_details,
    normalize_phone,
    validate_apartment,
    validate_building,
    validate_customer_name,
    validate_celebration_date,
    validate_delivery_time_custom,
    validate_person_name,
    validate_short_text,
    validate_street_name,
)

logger = logging.getLogger(__name__)
router = Router()


class AddCelebration(StatesGroup):
    recipient_role = State()
    recipient_name_custom = State()
    celebration_date = State()
    style_preference = State()
    taboo_tags = State()


class Checkout(StatesGroup):
    customer_name_custom = State()
    customer_phone = State()
    delivery_street = State()
    delivery_building = State()
    delivery_apartment_custom = State()
    delivery_time_custom = State()


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
    if role == "Другое":
        await state.set_state(AddCelebration.recipient_name_custom)
        await callback.message.edit_text(
            f"Кто получательница? Коротко, до {MAX_RECIPIENT_NAME} символов.\n"
            "Пример: Сестра Лена, Коллега Анна"
        )
        await callback.answer()
        return
    await callback.message.edit_text(
        f"Кто получательница: {role}.\nВыбери имя на кнопках или «Другое имя»:",
        reply_markup=recipient_name_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("rname:"))
async def process_recipient_name_pick(callback: CallbackQuery, state: FSMContext) -> None:
    picked = callback.data.split(":", 1)[1]
    data = await state.get_data()
    role = data.get("recipient_role", "")
    if picked == "other":
        await state.set_state(AddCelebration.recipient_name_custom)
        await callback.message.edit_text(
            f"Введи имя для «{role}» (до {MAX_RECIPIENT_NAME} символов):"
        )
        await callback.answer()
        return

    await state.update_data(recipient_name=f"{role} {picked}")
    await state.set_state(AddCelebration.celebration_date)
    await callback.message.edit_text(
        "Дата праздника? Формат ДД.ММ\n"
        "Пример: 25.10 (день 1–31, месяц 1–12)"
    )
    await callback.answer()


@router.message(AddCelebration.recipient_name_custom)
async def process_recipient_name_custom(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    role = data.get("recipient_role", "")

    if role == "Другое":
        label = validate_short_text(message.text or "", max_len=MAX_RECIPIENT_NAME, min_len=3)
        if not label or not re.search(r"[A-Za-zА-Яа-яЁё]{2,}", label):
            await message.answer(
                f"Укажи, кто она, буквами — до {MAX_RECIPIENT_NAME} символов.\n"
                "Пример: Сестра Лена"
            )
            return
        await state.update_data(recipient_name=label)
    else:
        name = validate_person_name(message.text or "")
        if not name or len(name) > MAX_RECIPIENT_NAME:
            await message.answer(
                f"Имя буквами, 3–{MAX_RECIPIENT_NAME} символов.\n"
                "Пример: Катя, Мария"
            )
            return
        await state.update_data(recipient_name=f"{role} {name}")

    await state.set_state(AddCelebration.celebration_date)
    await message.answer(
        "Дата праздника? Формат ДД.ММ\n"
        "Пример: 25.10 (день 1–31, месяц 1–12)"
    )


@router.message(AddCelebration.celebration_date)
async def process_celebration_date(message: Message, state: FSMContext) -> None:
    celebration_date = validate_celebration_date(message.text or "")
    if not celebration_date:
        await message.answer(
            "Нужен формат ДД.ММ — только цифры и точка.\n"
            "День 1–31, месяц 1–12. Пример: 25.10"
        )
        return
    await state.update_data(celebration_date=celebration_date)
    await state.set_state(AddCelebration.style_preference)
    await message.answer(
        "Какой стиль цветов она предпочитает?",
        reply_markup=style_keyboard(),
    )


@router.callback_query(F.data.startswith("style:"), AddCelebration.style_preference)
async def process_style(callback: CallbackQuery, state: FSMContext) -> None:
    style = callback.data.split(":", 1)[1]
    await state.update_data(style_preference=style, taboo_selected=[])
    await state.set_state(AddCelebration.taboo_tags)
    await callback.message.edit_text(
        "Отметь ограничения и аллергии (можно несколько).\n"
        "Нажми «Готово», когда выберешь:",
        reply_markup=taboo_keyboard(set()),
    )
    await callback.answer()


async def _save_celebration(callback: CallbackQuery, state: FSMContext, taboo_tags: str | None) -> None:
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
    taboo_line = ""
    if taboo_tags:
        taboo_line = f"\n⛔ Исключили: {format_taboo_list(taboo_tags)}"
    await callback.message.edit_text(
        "Готово! Праздник сохранён ✅\n\n"
        f"👤 {data['recipient_name']}\n"
        f"📅 {data['celebration_date']}\n"
        f"🌸 Стиль: {style_label}{taboo_line}\n\n"
        "За 5 дней до даты пришлю подборку букетов и кнопки оплаты в 1 клик."
    )
    logger.info("Celebration %s created for user %s", celebration_id, callback.from_user.id)


@router.callback_query(F.data.startswith("taboo:"), AddCelebration.taboo_tags)
async def process_taboo(callback: CallbackQuery, state: FSMContext) -> None:
    action = callback.data
    data = await state.get_data()
    selected = set(data.get("taboo_selected") or [])

    if action == "taboo:done":
        taboo_tags = ",".join(sorted(selected)) if selected else None
        await _save_celebration(callback, state, taboo_tags)
        await callback.answer("Сохранено")
        return

    if action == "taboo:clear":
        await state.update_data(taboo_selected=[])
        await callback.message.edit_reply_markup(reply_markup=taboo_keyboard(set()))
        await callback.answer("Ограничений нет")
        return

    if action.startswith("taboo:toggle:"):
        tag = action.split(":", 2)[2]
        if tag in selected:
            selected.remove(tag)
        else:
            selected.add(tag)
        await state.update_data(taboo_selected=list(selected))
        await callback.message.edit_reply_markup(reply_markup=taboo_keyboard(selected))
        picked = format_taboo_list(",".join(sorted(selected))) if selected else "пока ничего"
        await callback.answer(f"Выбрано: {picked}")
        return

    await callback.answer()


@router.message(F.text == "📅 Мои праздники")
async def list_celebrations(message: Message) -> None:
    items = await get_user_celebrations(message.from_user.id)
    if not items:
        await message.answer("Пока нет сохранённых праздников. Нажми «➕ Добавить праздник».")
        return
    lines = ["📅 Твои праздники:\n"]
    for item in items:
        style = STYLE_LABELS.get(item["style_preference"], item["style_preference"])
        taboo = f"\n   ⛔ {format_taboo_list(item['taboo_tags'])}" if item.get("taboo_tags") else ""
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
    await message.answer(
        "🧪 Демо: так выглядит напоминание за 5 дней до праздника.\n\n"
        f"{format_reminder_details(celebration)}"
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
    user = await get_user(callback.from_user.id)
    suggested_name = (user or {}).get("customer_name") or callback.from_user.full_name
    await state.update_data(
        order_id=order_id,
        celebration_id=celebration_id,
        suggested_name=suggested_name,
    )

    await callback.message.answer(
        f"Отличный выбор — {BUDGET_LABELS[amount]} ({amount:,} ₽).".replace(",", " ")
    )
    await callback.answer()

    if not (user or {}).get("customer_name"):
        await state.set_state(Checkout.customer_name_custom)
        hint = ""
        if suggested_name and validate_customer_name(suggested_name):
            hint = f"\nНапример: {suggested_name}"
        await callback.message.answer(
            f"Как тебя зовут? Одно слово, до {MAX_CUSTOMER_NAME} букв.{hint}"
        )
        return

    if not (user or {}).get("phone"):
        await state.set_state(Checkout.customer_phone)
        await callback.message.answer(
            "Телефон для курьера — нажми кнопку или введи номер (+7...):",
            reply_markup=phone_keyboard(),
        )
        return

    await _prompt_delivery_address(callback.message, state)


async def _prompt_delivery_district(message: Message, state: FSMContext) -> None:
    await state.set_state(None)
    await message.answer(
        "Выбери округ доставки в Москве:",
        reply_markup=district_keyboard(),
    )


@router.message(Checkout.customer_name_custom)
async def process_customer_name_custom(message: Message, state: FSMContext) -> None:
    name = validate_customer_name(message.text or "")
    if not name:
        await message.answer(
            f"Имя: одно слово, 2–{MAX_CUSTOMER_NAME} букв, без пробелов.\n"
            "Пример: Роман, Олег"
        )
        return

    await update_user_profile(message.from_user.id, customer_name=name)
    user = await get_user(message.from_user.id)
    if user and user.get("phone"):
        await _prompt_delivery_district(message, state)
        return

    await state.set_state(Checkout.customer_phone)
    await message.answer(
        "Телефон для курьера — нажми кнопку или введи номер (+7...):",
        reply_markup=phone_keyboard(),
    )


async def _prompt_delivery_address(message: Message, state: FSMContext) -> None:
    await _prompt_delivery_district(message, state)


@router.message(Checkout.customer_phone, F.contact)
async def process_customer_contact(message: Message, state: FSMContext) -> None:
    if message.contact and message.contact.user_id != message.from_user.id:
        await message.answer("Отправь свой номер, не чужой.", reply_markup=phone_keyboard())
        return
    phone = normalize_phone(message.contact.phone_number if message.contact else "")
    if not phone:
        await message.answer("Не удалось прочитать номер. Введи вручную: +7 916 123-45-67")
        return
    await update_user_profile(message.from_user.id, phone=phone)
    await _prompt_delivery_address(message, state)


@router.message(Checkout.customer_phone)
async def process_customer_phone_text(message: Message, state: FSMContext) -> None:
    phone = normalize_phone(message.text or "")
    if not phone:
        await message.answer(
            "Неверный номер. Пример: +7 916 123-45-67",
            reply_markup=phone_keyboard(),
        )
        return
    await update_user_profile(message.from_user.id, phone=phone)
    await _prompt_delivery_address(message, state)


@router.callback_query(F.data.startswith("district:"))
async def process_district(callback: CallbackQuery, state: FSMContext) -> None:
    district = callback.data.split(":", 1)[1]
    await state.update_data(delivery_district=district)
    await state.set_state(Checkout.delivery_street)
    await callback.message.answer(
        f"Округ: {district}.\n"
        f"Улица (до {MAX_STREET} символов), без «ул.»:\n"
        "Пример: Преображенский Вал"
    )
    await callback.answer()


@router.message(Checkout.delivery_street)
async def process_street(message: Message, state: FSMContext) -> None:
    street = validate_street_name(message.text or "")
    if not street:
        await message.answer(
            f"Укажи улицу буквами, 3–{MAX_STREET} символов.\n"
            "Пример: Тверская"
        )
        return
    await state.update_data(delivery_street=street)
    await state.set_state(Checkout.delivery_building)
    await message.answer(
        f"Дом и корпус (до {MAX_BUILDING} символов):\n"
        "Пример: 12 или 12к2"
    )


@router.message(Checkout.delivery_building)
async def process_building(message: Message, state: FSMContext) -> None:
    building = validate_building(message.text or "")
    if not building:
        await message.answer(
            f"Укажи номер дома с цифрой, до {MAX_BUILDING} символов.\n"
            "Пример: 12"
        )
        return
    await state.update_data(delivery_building=building)
    await state.set_state(None)
    await message.answer("Квартира:", reply_markup=apartment_keyboard())


@router.callback_query(F.data.startswith("apt:"))
async def process_apartment_pick(callback: CallbackQuery, state: FSMContext) -> None:
    action = callback.data.split(":", 1)[1]
    if action == "custom":
        await state.set_state(Checkout.delivery_apartment_custom)
        await callback.message.answer(f"Номер квартиры (до {MAX_APARTMENT} символов):")
        await callback.answer()
        return

    await state.update_data(delivery_apartment=None)
    await callback.message.answer(
        "Выбери удобный интервал доставки:",
        reply_markup=delivery_time_keyboard(),
    )
    await callback.answer()


@router.message(Checkout.delivery_apartment_custom)
async def process_apartment_custom(message: Message, state: FSMContext) -> None:
    apartment = validate_apartment(message.text or "")
    if not apartment:
        await message.answer(f"Квартира: цифры/буквы, до {MAX_APARTMENT} символов. Пример: 45")
        return
    await state.update_data(delivery_apartment=apartment)
    await state.set_state(None)
    await message.answer(
        "Выбери удобный интервал доставки:",
        reply_markup=delivery_time_keyboard(),
    )


@router.callback_query(F.data.startswith("dtime:"))
async def process_delivery_time_pick(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    picked = callback.data.split(":", 1)[1]
    if picked == "other":
        await state.set_state(Checkout.delivery_time_custom)
        await callback.message.answer("Введи интервал, например 09:00–11:00")
        await callback.answer()
        return
    await state.update_data(delivery_time=picked)
    await callback.answer()
    await _finalize_checkout(callback.message, state, bot)


@router.message(Checkout.delivery_time_custom)
async def process_delivery_time_custom(message: Message, state: FSMContext, bot: Bot) -> None:
    delivery_time = validate_delivery_time_custom(message.text or "")
    if not delivery_time:
        await message.answer("Формат: 08:00–12:00. Время «с» должно быть раньше «до».")
        return
    await state.update_data(delivery_time=delivery_time)
    await _finalize_checkout(message, state, bot)


async def _finalize_checkout(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    order_id = data.get("order_id")
    celebration_id = data.get("celebration_id")
    delivery_time = data.get("delivery_time")
    if not order_id or not celebration_id or not delivery_time:
        await message.answer("Сессия заказа сброшена. Начни с напоминания.")
        await state.clear()
        return

    delivery_address = compose_delivery_address(
        data.get("delivery_district", ""),
        data.get("delivery_street", ""),
        data.get("delivery_building", ""),
        data.get("delivery_apartment"),
    )
    if not delivery_address:
        await message.answer("Не удалось собрать адрес. Начни оформление заново.")
        await state.clear()
        return

    user = await get_user(message.from_user.id)
    customer_name = (user or {}).get("customer_name")
    customer_phone = (user or {}).get("phone")

    await update_order_delivery(
        order_id,
        delivery_address,
        delivery_time,
        customer_name=customer_name,
        customer_phone=customer_phone,
    )
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
    await send_admin_logistics(bot, order, celebration)
    logger.info("Order %s paid (test) for user %s", order_id, callback.from_user.id)


async def send_admin_logistics(bot: Bot, order: dict, celebration: dict) -> None:
    if not ADMIN_CHAT_ID:
        return
    phone = order.get("customer_phone") or ""
    text = (
        f"📦 Логистика заказ #{order['order_id']}\n"
        f"Заказчик: {order.get('customer_name') or '—'}\n"
        f"Телефон: {format_phone(phone) if phone else '—'}\n"
        f"Адрес: {order.get('delivery_address')}\n"
        f"Интервал: {order.get('delivery_time')}\n"
        f"Получатель: {celebration['recipient_name']}"
    )
    try:
        await bot.send_message(int(ADMIN_CHAT_ID), text)
    except Exception:
        logger.exception("Failed to send logistics for order %s", order["order_id"])


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

def _photo_media(source: str | Path, caption: str | None = None) -> InputMediaPhoto:
    if isinstance(source, Path):
        return InputMediaPhoto(media=FSInputFile(source), caption=caption)
    return InputMediaPhoto(media=source, caption=caption)


async def send_reminder(bot: Bot, celebration: dict) -> None:
    user_id = celebration["user_id"]
    display = build_reminder_display(celebration.get("style_preference"), celebration.get("taboo_tags"))

    if display.mode == "budget_photos":
        media_bouquets = list(display.photos)
        intro = (
            "Три фото — Эконом, Бизнес и Премиум в выбранном стиле.\n"
            f"{display.packaging_note}"
        )
    else:
        media_bouquets = [card.hero for card in display.cards]
        lines = [display.packaging_note, ""]
        for card in display.cards:
            lines.append(f"{card.style_label} (на фото — бизнес):")
            for tier in card.tiers:
                label = BUDGET_LABELS.get(tier.budget, "")
                lines.append(f"  • {label} — {tier.description} ({format_price(tier.budget)})")
            lines.append("")
        intro = "\n".join(lines).strip()

    price_lines = "\n".join(
        f"  {index}. {bouquet.name} — {format_price(bouquet.budget)}"
        for index, bouquet in enumerate(media_bouquets, start=1)
    )
    text = (
        f"🚨 Привет! Через 5 дней праздник:\n\n"
        f"{format_reminder_details(celebration)}\n\n"
        f"{intro}\n\n"
        f"💐 Варианты и цены:\n{price_lines}\n\n"
        "Выбери бюджет кнопкой ниже:"
    )

    try:
        media = [
            _photo_media(bouquet.image_source(), caption=bouquet.caption())
            for bouquet in media_bouquets
        ]
        await bot.send_media_group(user_id, media=media)
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
    date_display = format_celebration_date(celebration["celebration_date"])
    text = (
        f"⏰ Через 3 дня — {celebration['recipient_name']} ({date_display}).\n"
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

from __future__ import annotations

import logging
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.filters.command import CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, InputMediaPhoto, Message

from bot_display import (
    build_recipient_name,
    celebration_title,
    format_celebration_line_html,
    recipient_display_name,
    style_label_for,
)
from choices import (
    CALENDAR_IDEAL_DATES,
    EVENT_AUTO_DATES,
    EVENT_TYPES,
    MAX_CUSTOM_TEXT,
    MAX_RECIPIENT_FIO,
    ONBOARDING_START_HINT,
    PEAK_DATES_MARKETING,
    RECIPIENT_ROLE_CUSTOM,
    WELCOME_TEXT,
    calendar_onboarding_nudge,
    referral_bonus_granted_text,
    referral_bound_hint,
    referral_friend_joined_text,
    referral_invite_text,
)
from bouquets import build_reminder_display
from config import ADMIN_CHAT_ID, BUDGETS, BUDGET_LABELS
from database import (
    add_celebration,
    bind_referrer,
    consume_referral_credit,
    create_order,
    delete_celebration,
    get_celebration,
    get_celebration_latest_order,
    get_order,
    get_referral_credit,
    get_user,
    get_user_celebrations,
    try_grant_referral_bonus,
    update_celebration,
    update_celebration_delivery,
    update_order_delivery,
    update_order_discount,
    update_order_payment,
    update_user_profile,
    upsert_user,
)
from delivery_helpers import (
    celebration_has_saved_delivery,
    delivery_from_latest_order,
    delivery_summary,
)
from keyboards import (
    apartment_keyboard,
    budget_keyboard,
    celebration_edit_menu_keyboard,
    celebrations_edit_keyboard,
    comment_skip_keyboard,
    recipient_phone_keyboard,
    delivery_reuse_keyboard,
    delivery_time_keyboard,
    event_keyboard,
    main_menu_keyboard,
    phone_keyboard,
    recipient_keyboard,
    style_keyboard,
    taboo_keyboard,
    test_pay_keyboard,
)
from payment_quips import payment_success_message
from payments import create_payment
from referrals import order_charge_amount, parse_referral_start, referral_link
from taboos import format_taboo_list
from utils import (
    compose_delivery_address,
    days_until,
    format_phone,
    format_celebration_date,
    format_price,
    format_reminder_details,
    normalize_phone,
    save_celebration_flash_message,
    validate_apartment,
    validate_building,
    validate_celebration_date,
    validate_custom_text,
    validate_customer_name,
    validate_delivery_time_custom,
    validate_order_comment,
    validate_recipient_name,
    validate_russian_mobile,
    validate_street_name,
)

logger = logging.getLogger(__name__)
router = Router()


class AddCelebration(StatesGroup):
    recipient_role_custom = State()
    recipient_fio = State()
    event_custom = State()
    celebration_date = State()
    taboo_tags = State()


class Checkout(StatesGroup):
    customer_name_custom = State()
    customer_phone = State()
    delivery_street = State()
    delivery_building = State()
    delivery_apartment_custom = State()
    delivery_time_custom = State()
    recipient_phone = State()
    delivery_comment = State()


async def _ensure_celebration_delivery(celebration: dict, user_id: int) -> dict:
    if celebration_has_saved_delivery(celebration):
        return celebration
    payload = delivery_from_latest_order(await get_celebration_latest_order(celebration["id"]))
    if not payload or not payload.get("delivery_street"):
        return celebration
    await update_celebration_delivery(
        celebration["id"],
        user_id,
        payload["delivery_street"],
        payload["delivery_building"],
        payload.get("delivery_corps"),
        payload.get("delivery_apartment"),
        payload["delivery_time"],
        payload.get("delivery_comment"),
        payload.get("recipient_contact_phone"),
    )
    refreshed = await get_celebration(celebration["id"])
    return refreshed or celebration


async def _delivery_defaults(celebration_id: int, user_id: int) -> dict | None:
    celebration = await get_celebration(celebration_id)
    if not celebration:
        return None
    celebration = await _ensure_celebration_delivery(celebration, user_id)
    if not celebration_has_saved_delivery(celebration):
        return None
    return {
        "delivery_street": celebration["delivery_street"],
        "delivery_building": celebration["delivery_building"],
        "delivery_corps": celebration.get("delivery_corps"),
        "delivery_apartment": celebration.get("delivery_apartment"),
        "delivery_time": celebration.get("delivery_time") or "",
        "delivery_comment": celebration.get("delivery_comment") or "",
        "recipient_contact_phone": celebration.get("delivery_contact_phone") or "",
    }


def _apply_delivery_defaults(data: dict) -> dict:
    return {
        "delivery_street": data["delivery_street"],
        "delivery_building": data["delivery_building"],
        "delivery_corps": data.get("delivery_corps"),
        "delivery_apartment": data.get("delivery_apartment"),
        "delivery_time": data.get("delivery_time") or "",
        "delivery_comment": data.get("delivery_comment") or "",
        "recipient_contact_phone": data.get("recipient_contact_phone") or "",
    }


async def _apply_celebration_update(celebration_id: int, user_id: int, **changes) -> bool:
    celebration = await get_celebration(celebration_id)
    if not celebration or celebration["user_id"] != user_id:
        return False
    role = changes.get("recipient_role", celebration.get("recipient_role"))
    role_custom = changes.get("recipient_role_custom", celebration.get("recipient_role_custom"))
    fio = changes.get("recipient_fio", celebration.get("recipient_fio"))
    recipient_name = build_recipient_name(role or "", role_custom, fio or "")
    return await update_celebration(
        celebration_id,
        user_id,
        recipient_name=recipient_name,
        celebration_date=changes.get("celebration_date", celebration["celebration_date"]),
        style_preference=changes.get("style_preference", celebration.get("style_preference") or ""),
        taboo_tags=changes.get("taboo_tags", celebration.get("taboo_tags")),
        recipient_role=role,
        recipient_role_custom=role_custom,
        recipient_fio=fio,
        event_type=changes.get("event_type", celebration.get("event_type")),
        event_custom=changes.get("event_custom", celebration.get("event_custom")),
    )


async def _show_edit_menu(message: Message, celebration_id: int, note: str = "") -> None:
    celebration = await get_celebration(celebration_id)
    if not celebration:
        await message.answer("Праздник не найден.")
        return
    prefix = f"{note}\n\n" if note else ""
    await message.answer(
        f"{prefix}Что изменить — {celebration_title(celebration)}?",
        reply_markup=celebration_edit_menu_keyboard(celebration_id),
    )


async def _go_to_style_step(target: Message, state: FSMContext) -> None:
    await state.update_data(style_selected=[])
    await state.set_state(None)
    await target.answer(
        "Какой эффект от подарка?\nНе про цветы — про её реакцию.\nМожно выбрать несколько:",
        reply_markup=style_keyboard(set()),
    )


async def _go_to_taboo_step(callback: CallbackQuery, state: FSMContext, style_pref: str) -> None:
    await state.update_data(style_preference=style_pref, taboo_selected=[])
    await state.set_state(AddCelebration.taboo_tags)
    label = style_label_for({"style_preference": style_pref})
    await callback.message.edit_text(
        f"Эффект: {label}\n\n"
        "Ограничения (можно несколько). «Готово» — сохранить выбор, «Без ограничений» — пропустить:",
        reply_markup=taboo_keyboard(set()),
    )


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, command: CommandObject) -> None:
    await state.clear()
    await upsert_user(message.from_user.id, message.from_user.username)
    referrer_id = parse_referral_start(command.args)
    if referrer_id:
        bound = await bind_referrer(message.from_user.id, referrer_id)
        if bound:
            await message.answer(referral_bound_hint())
    await message.answer(WELCOME_TEXT, reply_markup=main_menu_keyboard())
    await message.answer(
        f"{ONBOARDING_START_HINT}\n\n{PEAK_DATES_MARKETING}\n\nНачни с добавления первого праздника 👇"
    )


@router.message(F.text == "🤝 Спасти друга")
async def referral_invite(message: Message, bot: Bot) -> None:
    me = await bot.get_me()
    if not me.username:
        await message.answer("Не могу сформировать ссылку — у бота нет username в BotFather.")
        return
    link = referral_link(me.username, message.from_user.id)
    await message.answer(referral_invite_text(link))
    credit = await get_referral_credit(message.from_user.id)
    if credit:
        await message.answer(
            f"На твоём счёте скидка {format_price(credit)} — применится при следующей оплате."
        )


@router.message(F.text == "➕ Добавить праздник")
async def add_celebration_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    items = await get_user_celebrations(message.from_user.id)
    intro = "Кого поздравляем?"
    if 0 < len(items) < CALENDAR_IDEAL_DATES:
        intro = f"{calendar_onboarding_nudge(len(items))}\n\n{intro}"
    await message.answer(intro, reply_markup=recipient_keyboard())


@router.callback_query(F.data.startswith("recipient:"))
async def process_recipient(callback: CallbackQuery, state: FSMContext) -> None:
    role = callback.data.split(":", 1)[1]
    await state.update_data(recipient_role=role)
    data = await state.get_data()
    edit_id = data.get("edit_celebration_id")
    if role == RECIPIENT_ROLE_CUSTOM:
        await state.set_state(AddCelebration.recipient_role_custom)
        await callback.message.edit_text("Кого поздравляем?")
        await callback.answer()
        return
    if edit_id and data.get("edit_field") == "role":
        await _apply_celebration_update(edit_id, callback.from_user.id, recipient_role=role, recipient_role_custom=None)
        await state.clear()
        await callback.message.edit_text(f"Сохранено: {role}")
        await _show_edit_menu(callback.message, edit_id)
        await callback.answer()
        return
    await state.set_state(AddCelebration.recipient_fio)
    await callback.message.edit_text(f"Кого поздравляем: {role}.\nИмя:")
    await callback.answer()


@router.message(AddCelebration.recipient_role_custom)
async def process_recipient_role_custom(message: Message, state: FSMContext) -> None:
    custom = validate_custom_text(message.text or "", MAX_CUSTOM_TEXT)
    if not custom:
        await message.answer("Коротко, только буквы.")
        return
    await state.update_data(recipient_role_custom=custom)
    data = await state.get_data()
    edit_id = data.get("edit_celebration_id")
    if edit_id and data.get("edit_field") == "role":
        await _apply_celebration_update(
            edit_id,
            message.from_user.id,
            recipient_role=RECIPIENT_ROLE_CUSTOM,
            recipient_role_custom=custom,
        )
        await state.clear()
        await message.answer(f"Сохранено: {custom}")
        await _show_edit_menu(message, edit_id)
        return
    await state.set_state(AddCelebration.recipient_fio)
    await message.answer("Имя:")


@router.message(AddCelebration.recipient_fio)
async def process_recipient_fio(message: Message, state: FSMContext) -> None:
    fio = validate_recipient_name(message.text or "", MAX_RECIPIENT_FIO)
    if not fio:
        await message.answer("Имя: от 1 до 3 слов, только буквы.\nПример: Мария или Мария Ивановна")
        return
    await state.update_data(recipient_fio=fio)
    data = await state.get_data()
    edit_id = data.get("edit_celebration_id")
    if edit_id and data.get("edit_field") == "name":
        await _apply_celebration_update(edit_id, message.from_user.id, recipient_fio=fio)
        await state.clear()
        await message.answer(f"Сохранено: {fio}")
        await _show_edit_menu(message, edit_id)
        return
    await state.set_state(None)
    await message.answer("С чем поздравляем?", reply_markup=event_keyboard())


@router.callback_query(F.data.startswith("event:"))
async def process_event(callback: CallbackQuery, state: FSMContext) -> None:
    event_type = callback.data.split(":", 1)[1]
    await state.update_data(event_type=event_type, event_custom=None)
    data = await state.get_data()
    edit_id = data.get("edit_celebration_id")

    if event_type == "other":
        await state.set_state(AddCelebration.event_custom)
        await callback.message.edit_text("С чем поздравляем?")
        await callback.answer()
        return

    if event_type in EVENT_AUTO_DATES:
        auto_date = EVENT_AUTO_DATES[event_type]
        await state.update_data(celebration_date=auto_date)
        if edit_id and data.get("edit_field") == "event":
            await _apply_celebration_update(
                edit_id,
                callback.from_user.id,
                event_type=event_type,
                event_custom=None,
                celebration_date=auto_date,
            )
            await state.clear()
            await callback.message.edit_text(f"Сохранено: {EVENT_TYPES[event_type]}")
            await _show_edit_menu(callback.message, edit_id)
            await callback.answer()
            return
        await _go_to_style_step(callback.message, state)
        await callback.answer()
        return

    if edit_id and data.get("edit_field") == "event":
        await state.update_data(edit_field="event_date")
        await state.set_state(AddCelebration.celebration_date)
        await callback.message.edit_text(
            f"С чем поздравляем: {EVENT_TYPES[event_type]}.\n"
            "Дата ДД.ММ (пример: 25.10):"
        )
        await callback.answer()
        return

    await state.set_state(AddCelebration.celebration_date)
    await callback.message.edit_text(
        f"С чем поздравляем: {EVENT_TYPES[event_type]}.\n"
        "Дата ДД.ММ (пример: 25.10):"
    )
    await callback.answer()


@router.message(AddCelebration.event_custom)
async def process_event_custom(message: Message, state: FSMContext) -> None:
    custom = validate_custom_text(message.text or "", MAX_CUSTOM_TEXT)
    if not custom:
        await message.answer("Коротко, только буквы.")
        return
    await state.update_data(event_custom=custom)
    data = await state.get_data()
    edit_id = data.get("edit_celebration_id")
    if edit_id and data.get("edit_field") == "event":
        await state.update_data(edit_field="event_date")
        await state.set_state(AddCelebration.celebration_date)
        await message.answer("Дата праздника ДД.ММ (пример: 25.10):")
        return
    await state.set_state(AddCelebration.celebration_date)
    await message.answer("Дата праздника ДД.ММ (пример: 25.10):")


@router.message(AddCelebration.celebration_date)
async def process_celebration_date(message: Message, state: FSMContext) -> None:
    celebration_date = validate_celebration_date(message.text or "")
    if not celebration_date:
        await message.answer("Формат ДД.ММ. Пример: 25.10")
        return
    await state.update_data(celebration_date=celebration_date)
    data = await state.get_data()
    edit_id = data.get("edit_celebration_id")
    edit_field = data.get("edit_field")
    if edit_id and edit_field in ("date", "event_date"):
        changes: dict = {"celebration_date": celebration_date}
        if edit_field == "event_date":
            changes["event_type"] = data.get("event_type")
            changes["event_custom"] = data.get("event_custom")
        await _apply_celebration_update(edit_id, message.from_user.id, **changes)
        await state.clear()
        await message.answer(f"Сохранено: {format_celebration_date(celebration_date)}")
        await _show_edit_menu(message, edit_id)
        return
    await _go_to_style_step(message, state)


@router.callback_query(F.data.startswith("style:"))
async def process_style(callback: CallbackQuery, state: FSMContext) -> None:
    action = callback.data
    data = await state.get_data()
    selected = set(data.get("style_selected") or [])

    if action == "style:any":
        style_pref = ""
        edit_id = data.get("edit_celebration_id")
        if edit_id and data.get("edit_field") == "style":
            await _apply_celebration_update(edit_id, callback.from_user.id, style_preference=style_pref)
            await state.clear()
            await callback.message.edit_text("Сохранено: подберём сами")
            await _show_edit_menu(callback.message, edit_id)
            await callback.answer()
            return
        await _go_to_taboo_step(callback, state, style_pref)
        await callback.answer()
        return

    if action == "style:done":
        style_pref = ",".join(sorted(selected)) if selected else ""
        edit_id = data.get("edit_celebration_id")
        if edit_id and data.get("edit_field") == "style":
            await _apply_celebration_update(edit_id, callback.from_user.id, style_preference=style_pref)
            await state.clear()
            label = style_label_for({"style_preference": style_pref})
            await callback.message.edit_text(f"Сохранено: {label}")
            await _show_edit_menu(callback.message, edit_id)
            await callback.answer()
            return
        await _go_to_taboo_step(callback, state, style_pref)
        await callback.answer()
        return

    if action.startswith("style:toggle:"):
        key = action.split(":", 2)[2]
        if key in selected:
            selected.remove(key)
        else:
            selected.add(key)
        await state.update_data(style_selected=list(selected))
        await callback.message.edit_reply_markup(reply_markup=style_keyboard(selected))
        await callback.answer()
        return
    await callback.answer()


async def _save_celebration(callback: CallbackQuery, state: FSMContext, taboo_tags: str | None) -> None:
    data = await state.get_data()
    edit_id = data.get("edit_celebration_id")
    if edit_id and data.get("edit_field") == "taboo":
        ok = await _apply_celebration_update(edit_id, callback.from_user.id, taboo_tags=taboo_tags)
        await state.clear()
        if ok:
            taboo_line = format_taboo_list(taboo_tags) or "без ограничений"
            await callback.message.edit_text(f"Сохранено: {taboo_line}")
            await _show_edit_menu(callback.message, edit_id)
        else:
            await callback.message.edit_text("Не удалось сохранить.")
        return

    role = data["recipient_role"]
    role_custom = data.get("recipient_role_custom")
    fio = data["recipient_fio"]
    recipient_name = build_recipient_name(role, role_custom, fio)
    celebration_id = await add_celebration(
        user_id=callback.from_user.id,
        recipient_name=recipient_name,
        celebration_date=data["celebration_date"],
        style_preference=data.get("style_preference") or "",
        taboo_tags=taboo_tags,
        recipient_role=role,
        recipient_role_custom=role_custom,
        recipient_fio=fio,
        event_type=data.get("event_type"),
        event_custom=data.get("event_custom"),
    )
    await state.clear()
    warn = save_celebration_flash_message(data["celebration_date"])
    style_label = style_label_for({"style_preference": data.get("style_preference") or ""})
    taboo_line = f"\n⛔ {format_taboo_list(taboo_tags)}" if taboo_tags else ""
    count = len(await get_user_celebrations(callback.from_user.id))
    granted = await try_grant_referral_bonus(callback.from_user.id)
    text = (
        "Готово! Праздник сохранён ✅\n\n"
        f"👤 {recipient_name}\n"
        f"📅 {format_celebration_date(data['celebration_date'])}\n"
        f"{style_label}{taboo_line}\n\n"
        f"{warn}\n\n{calendar_onboarding_nudge(count)}"
    )
    if granted:
        text += f"\n\n{referral_bonus_granted_text(granted[1])}"
    await callback.message.edit_text(text)
    if granted:
        try:
            await callback.bot.send_message(granted[0], referral_friend_joined_text(granted[1]))
        except Exception:
            logger.exception("Failed to notify referrer %s", granted[0])
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
        edit_id = data.get("edit_celebration_id")
        if edit_id and data.get("edit_field") == "taboo":
            await _save_celebration(callback, state, None)
            await callback.answer("Без ограничений")
            return
        await _save_celebration(callback, state, None)
        await callback.answer("Без ограничений")
        return
    if action.startswith("taboo:toggle:"):
        tag = action.split(":", 2)[2]
        if tag in selected:
            selected.remove(tag)
        else:
            selected.add(tag)
        await state.update_data(taboo_selected=list(selected))
        await callback.message.edit_reply_markup(reply_markup=taboo_keyboard(selected))
        await callback.answer()
        return
    await callback.answer()


@router.message(F.text == "📅 Мои праздники")
async def list_celebrations(message: Message) -> None:
    items = await get_user_celebrations(message.from_user.id)
    if not items:
        await message.answer("Пока нет праздников. Нажми «➕ Добавить праздник».")
        return
    items.sort(key=lambda c: (days_until(c["celebration_date"]), c.get("id", 0)))
    lines = ["📅 Твои праздники:\n", *[format_celebration_line_html(c) for c in items]]
    edit_items = [(c["id"], celebration_title(c)) for c in items]
    await message.answer(
        "\n".join(lines),
        reply_markup=celebrations_edit_keyboard(edit_items),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("edcel:"))
async def edit_celebration_menu(callback: CallbackQuery, state: FSMContext) -> None:
    celebration_id = int(callback.data.split(":")[1])
    celebration = await get_celebration(celebration_id)
    if not celebration or celebration["user_id"] != callback.from_user.id:
        await callback.answer("Не найден", show_alert=True)
        return
    await state.clear()
    await callback.message.answer(
        f"Редактирование: {celebration_title(celebration)}",
        reply_markup=celebration_edit_menu_keyboard(celebration_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("efld:"))
async def edit_celebration_field(callback: CallbackQuery, state: FSMContext) -> None:
    _, cid_str, field = callback.data.split(":", 2)
    celebration_id = int(cid_str)
    celebration = await get_celebration(celebration_id)
    if not celebration or celebration["user_id"] != callback.from_user.id:
        await callback.answer("Не найден", show_alert=True)
        return

    if field == "delete":
        ok = await delete_celebration(celebration_id, callback.from_user.id)
        if ok:
            await callback.message.edit_text(f"🗑 Удалено: {celebration_title(celebration)}")
            await callback.answer("Удалено")
        else:
            await callback.answer("Не удалось удалить", show_alert=True)
        return

    await state.update_data(edit_celebration_id=celebration_id, edit_field=field)

    if field == "role":
        await callback.message.edit_text("Кого поздравляем?", reply_markup=recipient_keyboard())
    elif field == "name":
        await state.set_state(AddCelebration.recipient_fio)
        await callback.message.edit_text("Имя:")
    elif field == "event":
        await callback.message.edit_text("С чем поздравляем?", reply_markup=event_keyboard())
    elif field == "date":
        await state.set_state(AddCelebration.celebration_date)
        await callback.message.edit_text(
            f"Дата праздника ДД.ММ (пример: {format_celebration_date(celebration['celebration_date'])}):"
        )
    elif field == "style":
        selected = set((celebration.get("style_preference") or "").split(",")) - {""}
        await state.update_data(style_selected=list(selected))
        await callback.message.edit_text(
            "Какой эффект от подарка?\nМожно выбрать несколько:",
            reply_markup=style_keyboard(selected),
        )
    elif field == "taboo":
        selected = {
            t.strip()
            for t in (celebration.get("taboo_tags") or "").split(",")
            if t.strip()
        }
        await state.update_data(taboo_selected=list(selected))
        await state.set_state(AddCelebration.taboo_tags)
        await callback.message.edit_text(
            "Ограничения (можно несколько). «Готово» — сохранить, «Без ограничений» — сбросить:",
            reply_markup=taboo_keyboard(selected),
        )
    await callback.answer()


async def _send_test_reminder(message: Message, bot: Bot) -> None:
    items = await get_user_celebrations(message.from_user.id)
    if not items:
        await message.answer("Сначала добавь праздник, потом «🔔 Тест подборки».")
        return
    items.sort(key=lambda c: days_until(c["celebration_date"]))
    celebration = {**items[0], "user_id": message.from_user.id}
    await message.answer(
        "🧪 Демо напоминания за 5 дней:\n\n" + format_reminder_details(celebration)
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
    await state.update_data(order_id=order_id, celebration_id=celebration_id)

    choice_text = f"Отличный выбор — {BUDGET_LABELS[amount]} ({format_price(amount)})."
    credit = await get_referral_credit(callback.from_user.id)
    if credit:
        applied = min(credit, amount)
        choice_text += (
            f"\n🎁 Скидка {format_price(applied)} → к оплате {format_price(amount - applied)}."
        )
    await callback.message.answer(choice_text)
    await callback.answer()

    if not (user or {}).get("customer_name"):
        await state.set_state(Checkout.customer_name_custom)
        await callback.message.answer(
            "Твоё имя для заказа — как к тебе обратится курьер.\n"
            "ФИО, три слова через пробел:"
        )
        return
    if not (user or {}).get("phone"):
        await state.set_state(Checkout.customer_phone)
        await callback.message.answer(
            "Телефон для курьера (+7 9…):",
            reply_markup=phone_keyboard(),
        )
        return
    await _start_delivery(callback.message, state, callback.from_user.id, celebration_id)


@router.message(Checkout.customer_name_custom)
async def process_customer_name_custom(message: Message, state: FSMContext) -> None:
    name = validate_customer_name(message.text or "")
    if not name:
        await message.answer("Три слова через пробел. Пример: Иван Иванович Иванов")
        return
    await update_user_profile(message.from_user.id, customer_name=name)
    user = await get_user(message.from_user.id)
    data = await state.get_data()
    celebration_id = data.get("celebration_id")
    if user and user.get("phone") and celebration_id:
        await _start_delivery(message, state, message.from_user.id, celebration_id)
        return
    await state.set_state(Checkout.customer_phone)
    await message.answer("Телефон для курьера:", reply_markup=phone_keyboard())


@router.message(Checkout.customer_phone, F.contact)
async def process_customer_contact(message: Message, state: FSMContext) -> None:
    if message.contact and message.contact.user_id != message.from_user.id:
        await message.answer("Отправь свой номер.", reply_markup=phone_keyboard())
        return
    phone = validate_russian_mobile(message.contact.phone_number if message.contact else "") or normalize_phone(
        message.contact.phone_number if message.contact else ""
    )
    if not phone:
        await message.answer("Не удалось прочитать номер. Введи: +7 9XX XXX-XX-XX")
        return
    await update_user_profile(message.from_user.id, phone=phone)
    data = await state.get_data()
    if data.get("celebration_id"):
        await _start_delivery(message, state, message.from_user.id, data["celebration_id"])


@router.message(Checkout.customer_phone)
async def process_customer_phone_text(message: Message, state: FSMContext) -> None:
    phone = validate_russian_mobile(message.text or "") or normalize_phone(message.text or "")
    if not phone:
        await message.answer("Мобильный РФ: +7 9XX XXX-XX-XX", reply_markup=phone_keyboard())
        return
    await update_user_profile(message.from_user.id, phone=phone)
    data = await state.get_data()
    if data.get("celebration_id"):
        await _start_delivery(message, state, message.from_user.id, data["celebration_id"])


async def _start_delivery(message: Message, state: FSMContext, user_id: int, celebration_id: int) -> None:
    defaults = await _delivery_defaults(celebration_id, user_id)
    if defaults:
        await state.update_data(delivery_defaults=defaults)
        await message.answer(
            "Данные с прошлого заказа.\n"
            f"{delivery_summary(defaults)}\n\n"
            "Ничего не изменилось?",
            reply_markup=delivery_reuse_keyboard(),
        )
        return
    await _prompt_street(message, state)


async def _prompt_street(message: Message, state: FSMContext) -> None:
    await state.set_state(Checkout.delivery_street)
    await message.answer(
        "Доставка по Москве.\n"
        "Улица, без «ул.»:\n"
        "Пример: Преображенский Вал"
    )


@router.callback_query(F.data.startswith("dlv:"))
async def process_delivery_reuse(callback: CallbackQuery, state: FSMContext) -> None:
    action = callback.data.split(":", 1)[1]
    if action == "new":
        await _prompt_street(callback.message, state)
        await callback.answer()
        return
    data = await state.get_data()
    defaults = data.get("delivery_defaults")
    if not defaults:
        await callback.answer("Нет сохранённого адреса", show_alert=True)
        return
    await state.update_data(**_apply_delivery_defaults(defaults))
    await callback.message.answer("Ок, адрес как в прошлый раз.")
    if defaults.get("delivery_time"):
        await _after_delivery_time(callback.message, state, callback.from_user.id)
    else:
        await callback.message.answer("Интервал доставки:", reply_markup=delivery_time_keyboard())
    await callback.answer()


@router.message(Checkout.delivery_street)
async def process_street(message: Message, state: FSMContext) -> None:
    street = validate_street_name(message.text or "")
    if not street:
        await message.answer("Улица: от 3 символов. Пример: Тверская")
        return
    await state.update_data(delivery_street=street)
    await state.set_state(Checkout.delivery_building)
    await message.answer("Дом и корпус:\nМожно 12к2")


@router.message(Checkout.delivery_building)
async def process_building(message: Message, state: FSMContext) -> None:
    building = validate_building(message.text or "")
    if not building:
        await message.answer("Дом с цифрой. Пример: 12к2")
        return
    await state.update_data(delivery_building=building, delivery_corps=None)
    await state.set_state(None)
    await message.answer("Квартира:", reply_markup=apartment_keyboard())


@router.callback_query(F.data.startswith("apt:"))
async def process_apartment_pick(callback: CallbackQuery, state: FSMContext) -> None:
    action = callback.data.split(":", 1)[1]
    if action == "custom":
        await state.set_state(Checkout.delivery_apartment_custom)
        await callback.message.answer("Номер квартиры:\nПример: 15")
        await callback.answer()
        return
    await state.update_data(delivery_apartment=None)
    await callback.message.answer("Интервал доставки:", reply_markup=delivery_time_keyboard())
    await callback.answer()


@router.message(Checkout.delivery_apartment_custom)
async def process_apartment_custom(message: Message, state: FSMContext) -> None:
    apartment = validate_apartment(message.text or "")
    if not apartment:
        await message.answer("Квартира: только цифры.")
        return
    await state.update_data(delivery_apartment=apartment)
    await state.set_state(None)
    await message.answer("Интервал доставки:", reply_markup=delivery_time_keyboard())


@router.callback_query(F.data.startswith("dtime:"))
async def process_delivery_time_pick(callback: CallbackQuery, state: FSMContext) -> None:
    picked = callback.data.split(":", 1)[1]
    if picked == "other":
        await state.set_state(Checkout.delivery_time_custom)
        await callback.message.answer("Интервал, например 09:00–11:00")
        await callback.answer()
        return
    await state.update_data(delivery_time=picked)
    await callback.answer()
    await _after_delivery_time(callback.message, state, callback.from_user.id)


@router.message(Checkout.delivery_time_custom)
async def process_delivery_time_custom(message: Message, state: FSMContext) -> None:
    delivery_time = validate_delivery_time_custom(message.text or "")
    if not delivery_time:
        await message.answer("Формат: 08:00–12:00")
        return
    await state.update_data(delivery_time=delivery_time)
    await _after_delivery_time(message, state, message.from_user.id)


async def _after_delivery_time(message: Message, state: FSMContext, user_id: int) -> None:
    data = await state.get_data()
    if data.get("recipient_contact_phone"):
        await _prompt_comment(message, state)
        return
    await _prompt_recipient_phone(message, state, user_id)


async def _prompt_recipient_phone(message: Message, state: FSMContext, user_id: int) -> None:
    data = await state.get_data()
    celebration = await get_celebration(data.get("celebration_id") or 0)
    name = recipient_display_name(celebration) if celebration else "получателя"
    user = await get_user(user_id)
    await state.set_state(Checkout.recipient_phone)
    text = f"Телефон {name} — кто встретит курьера:"
    if user and user.get("phone"):
        await message.answer(text, reply_markup=recipient_phone_keyboard())
    else:
        await message.answer(text)


@router.callback_query(F.data == "rcpt:same")
async def recipient_phone_same_as_customer(callback: CallbackQuery, state: FSMContext) -> None:
    user = await get_user(callback.from_user.id)
    phone = (user or {}).get("phone")
    if not phone:
        await callback.answer("Сначала укажи свой телефон", show_alert=True)
        return
    await state.update_data(recipient_contact_phone=phone)
    await state.set_state(None)
    await callback.answer()
    await _prompt_comment(callback.message, state)


@router.message(Checkout.recipient_phone)
async def process_recipient_phone(message: Message, state: FSMContext) -> None:
    phone = validate_russian_mobile(message.text or "") or normalize_phone(message.text or "")
    if not phone:
        await message.answer("Мобильный РФ: +7 9XX XXX-XX-XX", reply_markup=recipient_phone_keyboard())
        return
    await state.update_data(recipient_contact_phone=phone)
    await state.set_state(None)
    await _prompt_comment(message, state)


async def _prompt_comment(message: Message, state: FSMContext) -> None:
    await state.set_state(Checkout.delivery_comment)
    await message.answer(
        "Комментарий для курьера (домофон, подъезд…) — или пропусти:",
        reply_markup=comment_skip_keyboard(),
    )


@router.callback_query(F.data == "cmt:skip")
async def skip_comment(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await state.update_data(delivery_comment=None)
    await callback.answer()
    await _finalize_checkout(callback.message, state, bot)


@router.message(Checkout.delivery_comment)
async def process_comment(message: Message, state: FSMContext, bot: Bot) -> None:
    comment = validate_order_comment(message.text or "")
    await state.update_data(delivery_comment=comment)
    await _finalize_checkout(message, state, bot)


async def _finalize_checkout(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    order_id = data.get("order_id")
    celebration_id = data.get("celebration_id")
    delivery_time = data.get("delivery_time")
    if not order_id or not celebration_id or not delivery_time:
        await message.answer("Сессия сброшена. Начни с напоминания.")
        await state.clear()
        return

    delivery_address = compose_delivery_address(
        None,
        data.get("delivery_street", ""),
        data.get("delivery_building", ""),
        data.get("delivery_apartment"),
        data.get("delivery_corps"),
    )
    if not delivery_address:
        await message.answer("Проверь адрес. Начни оформление заново.")
        await state.clear()
        return

    user = await get_user(message.from_user.id)
    comment = data.get("delivery_comment")
    recipient_phone = data.get("recipient_contact_phone")
    if not recipient_phone:
        await message.answer("Укажи телефон получателя.")
        await _prompt_recipient_phone(message, state, message.from_user.id)
        return

    await update_order_delivery(
        order_id,
        delivery_address,
        delivery_time,
        customer_name=(user or {}).get("customer_name"),
        customer_phone=(user or {}).get("phone"),
        delivery_comment=comment,
        recipient_contact_phone=recipient_phone,
    )
    street = data.get("delivery_street", "")
    building = data.get("delivery_building", "")
    if street and building:
        await update_celebration_delivery(
            celebration_id,
            message.from_user.id,
            street,
            building,
            data.get("delivery_corps"),
            data.get("delivery_apartment"),
            delivery_time,
            comment,
            recipient_phone,
        )

    order = await get_order(order_id)
    celebration = await get_celebration(celebration_id)
    if not order or not celebration:
        await message.answer("Ошибка заказа. Начни заново.")
        await state.clear()
        return

    amount = order["budget_selected"]
    credit = await get_referral_credit(message.from_user.id)
    discount = min(credit, amount)
    if discount:
        await update_order_discount(order_id, discount)
    charge = order_charge_amount(amount, discount)

    try:
        payment = await create_payment(
            amount_rub=charge,
            description=f"Букет для {celebration['recipient_name']} — #{order_id}",
            return_url="https://t.me/",
            metadata={"order_id": order_id, "user_id": message.from_user.id},
        )
        await update_order_payment(order_id, "pending", payment["id"])
    except Exception:
        logger.exception("Payment failed order %s", order_id)
        await message.answer("Не удалось создать платёж. Попробуй позже.")
        await state.clear()
        return

    await state.clear()
    discount_line = ""
    if discount:
        discount_line = f"\nСкидка: −{format_price(discount)}\nК оплате: {format_price(charge)}"
    comment_line = f"\nКомментарий: {comment}" if comment else ""
    recipient_line = f"\nТелефон получателя: {format_phone(recipient_phone)}"

    if payment.get("test_mode"):
        await message.answer(
            f"Заказ #{order_id}\n{format_price(amount)}{discount_line}\n"
            f"{delivery_address}\n{delivery_time}{recipient_line}{comment_line}\n\n"
            "Тестовая оплата:",
            reply_markup=test_pay_keyboard(order_id),
        )
        return
    await message.answer(
        f"Заказ #{order_id}.{discount_line}\n{delivery_address}\n{delivery_time}"
        f"{recipient_line}{comment_line}\n\n{payment['confirmation_url']}"
    )


@router.callback_query(F.data.startswith("pay:test:"))
async def test_payment(callback: CallbackQuery, bot: Bot) -> None:
    order_id = int(callback.data.split(":")[2])
    order = await get_order(order_id)
    if not order or order["user_id"] != callback.from_user.id:
        await callback.answer("Заказ не найден.", show_alert=True)
        return

    await update_order_payment(order_id, "paid", order.get("yookassa_payment_id"))
    discount = int(order.get("discount_applied") or 0)
    if discount:
        await consume_referral_credit(callback.from_user.id, discount)
    celebration = await get_celebration(order["celebration_id"])
    if not celebration:
        await callback.answer("Ошибка данных.", show_alert=True)
        return

    style_label = style_label_for(celebration)
    budget_label = BUDGET_LABELS.get(order["budget_selected"], str(order["budget_selected"]))
    role = celebration.get("recipient_role") or ""
    quip = payment_success_message(role, order["budget_selected"])
    await callback.message.edit_text(
        f"✅ Оплата прошла!\n{quip}\n\n"
        f"Заказ #{order_id} в работе.\n"
        f"Доставка: {order['delivery_address']}, {order['delivery_time']}"
    )
    await callback.answer("Оплачено")
    await send_florist_task(bot, order_id, style_label, budget_label, celebration["celebration_date"])
    await send_admin_logistics(bot, order, celebration)


async def send_admin_logistics(bot: Bot, order: dict, celebration: dict) -> None:
    if not ADMIN_CHAT_ID:
        return
    customer_phone = order.get("customer_phone") or ""
    recipient_phone = order.get("recipient_contact_phone") or ""
    comment = order.get("delivery_comment") or ""
    recipient_name = recipient_display_name(celebration)
    text = (
        f"📦 Заказ #{order['order_id']}\n"
        f"Заказчик: {order.get('customer_name') or '—'}\n"
        f"Телефон заказчика: {format_phone(customer_phone) if customer_phone else '—'}\n"
        f"Имя получателя: {recipient_name}\n"
        f"Телефон получателя: {format_phone(recipient_phone) if recipient_phone else '—'}\n"
        f"Адрес: {order.get('delivery_address')}\n"
        f"Интервал: {order.get('delivery_time')}"
    )
    if comment:
        text += f"\nКомментарий: {comment}"
    try:
        await bot.send_message(int(ADMIN_CHAT_ID), text)
    except Exception:
        logger.exception("Logistics failed order %s", order["order_id"])


async def send_florist_task(
    bot: Bot,
    order_id: int,
    style_label: str,
    budget_label: str,
    celebration_date: str,
) -> None:
    if not ADMIN_CHAT_ID:
        return
    text = (
        f"Заказ №{order_id}. {style_label} ({budget_label}). "
        f"Готовность: {celebration_date} к 08:00"
    )
    try:
        await bot.send_message(int(ADMIN_CHAT_ID), text)
    except Exception:
        logger.exception("Florist task failed order %s", order_id)


def _photo_media(source: str | Path, caption: str | None = None) -> InputMediaPhoto:
    if isinstance(source, Path):
        return InputMediaPhoto(media=FSInputFile(source), caption=caption)
    return InputMediaPhoto(media=source, caption=caption)


async def send_reminder(bot: Bot, celebration: dict) -> None:
    user_id = celebration["user_id"]
    display = build_reminder_display(celebration.get("style_preference"), celebration.get("taboo_tags"))

    if display.mode == "budget_photos":
        media_bouquets = list(display.photos)
        intro = display.packaging_note
    else:
        media_bouquets = [card.hero for card in display.cards]
        lines = [display.packaging_note, ""]
        for card in display.cards:
            lines.append(f"{card.style_label}:")
            for tier in card.tiers:
                label = BUDGET_LABELS.get(tier.budget, "")
                lines.append(f"  • {label} — {tier.user_effect()} ({format_price(tier.budget)})")
            lines.append("")
        intro = "\n".join(lines).strip()

    tier_labels = ("Эконом", "Бизнес", "Премиум")
    price_lines = "\n".join(
        f"  {index}. {tier_labels[index - 1] if index <= len(tier_labels) else BUDGET_LABELS.get(b.budget, '')}"
        f" — {format_price(b.budget)}"
        for index, b in enumerate(media_bouquets, start=1)
    )
    text = (
        f"🚨 Через 5 дней праздник:\n\n"
        f"{format_reminder_details(celebration)}\n\n"
        f"{intro}\n\n"
        f"💐 Варианты:\n{price_lines}\n\n"
        "Выбери вариант:"
    )
    try:
        media = [
            _photo_media(
                b.image_source(),
                caption=f"{BUDGET_LABELS.get(b.budget, '')}\n{format_price(b.budget)}",
            )
            for b in media_bouquets
        ]
        await bot.send_media_group(user_id, media=media)
        await bot.send_message(user_id, text, reply_markup=budget_keyboard(celebration["id"]))
    except Exception:
        logger.exception("Reminder failed user %s", user_id)


async def send_payment_nudge(bot: Bot, celebration: dict, order: dict) -> None:
    user_id = celebration["user_id"]
    amount = order_charge_amount(order["budget_selected"], order.get("discount_applied"))
    date_display = format_celebration_date(celebration["celebration_date"])
    discount = int(order.get("discount_applied") or 0)
    discount_note = f" (−{format_price(discount)})" if discount else ""
    text = (
        f"⏰ Через 3 дня — {celebration['recipient_name']} ({date_display}).\n"
        f"Заказ #{order['order_id']} — {format_price(amount)}{discount_note}, не оплачен."
    )
    try:
        if order.get("yookassa_payment_id", "").startswith("test_"):
            await bot.send_message(user_id, text, reply_markup=test_pay_keyboard(order["order_id"]))
        else:
            await bot.send_message(user_id, text)
    except Exception:
        logger.exception("Nudge failed user %s", user_id)

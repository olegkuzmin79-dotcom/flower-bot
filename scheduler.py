from __future__ import annotations

import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import MSK_TZ, PAYMENT_NUDGE_DAYS_BEFORE, REMINDER_DAYS_BEFORE
from database import (
    get_all_celebrations,
    get_unpaid_order_for_celebration_year,
    mark_celebration_nudge_year,
    mark_celebration_reminder_year,
)
from handlers import send_payment_nudge, send_reminder
from utils import days_until, msk_today, next_occurrence

logger = logging.getLogger(__name__)


async def run_daily_jobs(bot: Bot) -> None:
    today = msk_today()
    celebrations = await get_all_celebrations()
    logger.info("Daily scan: %s celebrations, date=%s", len(celebrations), today)

    for celebration in celebrations:
        dd_mm = celebration["celebration_date"]
        remaining = days_until(dd_mm, today)
        occurrence = next_occurrence(dd_mm, today)
        year = occurrence.year

        if remaining == REMINDER_DAYS_BEFORE:
            if celebration.get("reminder_sent_year") == year:
                continue
            await send_reminder(bot, celebration)
            await mark_celebration_reminder_year(celebration["id"], year)
            logger.info(
                "5-day reminder sent: celebration=%s user=%s",
                celebration["id"],
                celebration["user_id"],
            )

        if remaining == PAYMENT_NUDGE_DAYS_BEFORE:
            if celebration.get("nudge_sent_year") == year:
                continue
            order = await get_unpaid_order_for_celebration_year(
                celebration["user_id"],
                celebration["id"],
            )
            if not order:
                continue
            await send_payment_nudge(bot, celebration, order)
            await mark_celebration_nudge_year(celebration["id"], year)
            logger.info(
                "3-day nudge sent: celebration=%s order=%s",
                celebration["id"],
                order["order_id"],
            )


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=MSK_TZ)
    scheduler.add_job(
        run_daily_jobs,
        CronTrigger(hour=9, minute=0, timezone=MSK_TZ),
        args=[bot],
        id="daily_reminders",
        replace_existing=True,
    )
    return scheduler

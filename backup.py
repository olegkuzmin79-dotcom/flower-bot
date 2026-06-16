"""Бэкап bot.db: локальная копия на диске + отправка в Telegram админу."""

from __future__ import annotations

import asyncio
import logging
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.types import FSInputFile

from admin_db import export_csv
from config import (
    ADMIN_CHAT_ID,
    BACKUP_DIR,
    BACKUP_KEEP_COUNT,
    DATABASE_PATH,
    MSK_TZ,
)

logger = logging.getLogger(__name__)


def _timestamp() -> str:
    now = datetime.now(ZoneInfo(MSK_TZ))
    return now.strftime("%Y%m%d_%H%M")


def create_db_backup_file() -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DATABASE_PATH}")
    dest = BACKUP_DIR / f"bot_{_timestamp()}.db"
    shutil.copy2(DATABASE_PATH, dest)
    logger.info("Backup saved: %s", dest)
    return dest


def prune_old_backups() -> int:
    if not BACKUP_DIR.exists():
        return 0
    files = sorted(BACKUP_DIR.glob("bot_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    removed = 0
    for path in files[BACKUP_KEEP_COUNT:]:
        path.unlink(missing_ok=True)
        removed += 1
    return removed


def create_csv_bundle_dir() -> Path:
    stamp = _timestamp()
    folder = BACKUP_DIR / f"export_{stamp}"
    folder.mkdir(parents=True, exist_ok=True)
    for name in ("clients", "celebrations", "orders"):
        (folder / f"{name}.csv").write_text(export_csv(name), encoding="utf-8-sig")
    return folder


async def send_backup_to_admin(bot: Bot, db_path: Path, reason: str = "scheduled") -> bool:
    if not ADMIN_CHAT_ID:
        logger.warning("ADMIN_CHAT_ID not set — backup file kept locally only")
        return False
    chat_id = int(ADMIN_CHAT_ID)
    caption = f"📦 Бэкап базы ({reason})\n{DATABASE_PATH.name}"
    try:
        await bot.send_document(chat_id, FSInputFile(db_path), caption=caption)
        export_dir = await asyncio.to_thread(create_csv_bundle_dir)
        for csv_path in sorted(export_dir.glob("*.csv")):
            await bot.send_document(
                chat_id,
                FSInputFile(csv_path),
                caption=f"CSV: {csv_path.name} (можно импортировать в Google Sheets)",
            )
        return True
    except Exception:
        logger.exception("Failed to send backup to Telegram")
        return False


async def run_backup(bot: Bot, reason: str = "scheduled") -> Path | None:
    try:
        db_path = await asyncio.to_thread(create_db_backup_file)
        await asyncio.to_thread(prune_old_backups)
        await send_backup_to_admin(bot, db_path, reason=reason)
        return db_path
    except Exception:
        logger.exception("Backup failed")
        return None

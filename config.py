import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

DEV_MODE = os.getenv("DEV", "0") == "1"

if DEV_MODE:
    BOT_TOKEN = (os.getenv("BOT_TOKEN_DEV") or os.getenv("BOT_TOKEN") or "").strip()
else:
    BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

TELEGRAM_PROXY = os.getenv("TELEGRAM_PROXY", "").strip() or None
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID", "")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY", "")
FLORIST_CHAT_ID = os.getenv("FLORIST_CHAT_ID", "")
ADMIN_CHAT_ID = os.getenv("FLORIST_CHAT_ID", "") or os.getenv("ADMIN_CHAT_ID", "")

USE_TEST_PAYMENTS = os.getenv("USE_TEST_PAYMENTS", "1") == "1"

_data_dir = os.getenv("DATA_DIR", "").strip()
DATA_DIR = Path(_data_dir) if _data_dir else BASE_DIR / "data"
ASSETS_DIR = BASE_DIR / "assets"
_db_path = os.getenv("DATABASE_PATH", "").strip()
DATABASE_PATH = Path(_db_path) if _db_path else DATA_DIR / ("bot_dev.db" if DEV_MODE else "bot.db")
BACKUP_DIR = DATA_DIR / "backups"
BACKUP_KEEP_COUNT = int(os.getenv("BACKUP_KEEP_COUNT", "14"))

ADMIN_WEB_ENABLED = os.getenv("ADMIN_WEB_ENABLED", "1") == "1"
SECRET_KEY = os.getenv("WEB_SECRET_KEY", "local-dev-change-me")
ADMIN_PASSWORD = (
    os.getenv("WEB_ADMIN_PASSWORD", "").strip()
    or os.getenv("ADMIN_PASSWORD", "").strip()
    or "flower"
)
WEB_PORT = int(os.getenv("PORT", os.getenv("WEB_PORT", "8080")))

BUDGETS = {
    "econom": 4500,
    "business": 7500,
    "premium": 12000,
}

BUDGET_LABELS = {
    4500: "Эконом",
    7500: "Бизнес",
    12000: "Премиум",
}

from choices import STYLE_LABELS

MSK_TZ = "Europe/Moscow"
REMINDER_DAYS_BEFORE = 5
PAYMENT_NUDGE_DAYS_BEFORE = 3

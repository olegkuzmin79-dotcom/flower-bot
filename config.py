import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
ASSETS_DIR = BASE_DIR / "assets"
DATABASE_PATH = DATA_DIR / "bot.db"

load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
TELEGRAM_PROXY = os.getenv("TELEGRAM_PROXY", "").strip() or None
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID", "")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY", "")
FLORIST_CHAT_ID = os.getenv("FLORIST_CHAT_ID", "")
ADMIN_CHAT_ID = os.getenv("FLORIST_CHAT_ID", "") or os.getenv("ADMIN_CHAT_ID", "")

USE_TEST_PAYMENTS = os.getenv("USE_TEST_PAYMENTS", "1") == "1"

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

STYLE_LABELS = {
    "classic": "Классика",
    "tender": "Нежность",
    "bright": "Яркий",
}

MSK_TZ = "Europe/Moscow"
REMINDER_DAYS_BEFORE = 5
PAYMENT_NUDGE_DAYS_BEFORE = 3

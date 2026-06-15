from __future__ import annotations

import logging
from typing import Any

import aiosqlite

from config import DATA_DIR, DATABASE_PATH

logger = logging.getLogger(__name__)


async def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                phone TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS celebrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                recipient_name TEXT NOT NULL,
                celebration_date TEXT NOT NULL,
                style_preference TEXT NOT NULL,
                taboo_tags TEXT,
                reminder_sent_year INTEGER,
                nudge_sent_year INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS orders (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                celebration_id INTEGER NOT NULL,
                budget_selected INTEGER NOT NULL,
                payment_status TEXT NOT NULL DEFAULT 'pending',
                yookassa_payment_id TEXT,
                delivery_address TEXT,
                delivery_time TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (celebration_id) REFERENCES celebrations(id)
            );

            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_user_id INTEGER NOT NULL,
                referred_user_id INTEGER NOT NULL UNIQUE,
                bonus_rub INTEGER NOT NULL,
                completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (referrer_user_id) REFERENCES users(user_id),
                FOREIGN KEY (referred_user_id) REFERENCES users(user_id)
            );
            """
        )
        await db.commit()
        await _migrate_schema(db)
    logger.info("Database initialized at %s", DATABASE_PATH)


async def _migrate_schema(db: aiosqlite.Connection) -> None:
    migrations = {
        "users": {
            "customer_name": "TEXT",
            "referred_by_user_id": "INTEGER",
            "referral_credit_rub": "INTEGER NOT NULL DEFAULT 0",
        },
        "orders": {
            "customer_name": "TEXT",
            "customer_phone": "TEXT",
            "discount_applied": "INTEGER NOT NULL DEFAULT 0",
            "delivery_comment": "TEXT",
            "recipient_contact_name": "TEXT",
            "recipient_contact_phone": "TEXT",
            "bouquet_style": "TEXT",
        },
        "celebrations": {
            "recipient_role": "TEXT",
            "recipient_role_custom": "TEXT",
            "recipient_fio": "TEXT",
            "event_type": "TEXT",
            "event_custom": "TEXT",
            "delivery_street": "TEXT",
            "delivery_building": "TEXT",
            "delivery_corps": "TEXT",
            "delivery_apartment": "TEXT",
            "delivery_time": "TEXT",
            "delivery_contact_name": "TEXT",
            "delivery_contact_phone": "TEXT",
            "delivery_comment": "TEXT",
        },
    }
    for table, columns in migrations.items():
        cursor = await db.execute(f"PRAGMA table_info({table})")
        existing = {row[1] for row in await cursor.fetchall()}
        for column, col_type in columns.items():
            if column not in existing:
                await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
    await db.commit()


async def get_user(user_id: int) -> dict[str, Any] | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def update_user_profile(
    user_id: int,
    customer_name: str | None = None,
    phone: str | None = None,
) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        if customer_name is not None:
            await db.execute(
                "UPDATE users SET customer_name = ? WHERE user_id = ?",
                (customer_name, user_id),
            )
        if phone is not None:
            await db.execute(
                "UPDATE users SET phone = ? WHERE user_id = ?",
                (phone, user_id),
            )
        await db.commit()


async def upsert_user(user_id: int, username: str | None) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO users (user_id, username)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET username = excluded.username
            """,
            (user_id, username),
        )
        await db.commit()


async def count_user_celebrations(user_id: int) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM celebrations WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        return int(row[0]) if row else 0


async def bind_referrer(user_id: int, referrer_user_id: int) -> bool:
    if user_id == referrer_user_id:
        return False
    async with aiosqlite.connect(DATABASE_PATH) as db:
        referrer = await db.execute(
            "SELECT user_id FROM users WHERE user_id = ?",
            (referrer_user_id,),
        )
        if not await referrer.fetchone():
            return False

        cursor = await db.execute(
            "SELECT referred_by_user_id FROM users WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        if row and row[0]:
            return False

        cursor = await db.execute(
            "SELECT COUNT(*) FROM celebrations WHERE user_id = ?",
            (user_id,),
        )
        if (await cursor.fetchone())[0]:
            return False

        await db.execute(
            "UPDATE users SET referred_by_user_id = ? WHERE user_id = ?",
            (referrer_user_id, user_id),
        )
        await db.commit()
        return True


async def get_referral_credit(user_id: int) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "SELECT referral_credit_rub FROM users WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        return int(row[0]) if row and row[0] else 0


async def try_grant_referral_bonus(referred_user_id: int) -> tuple[int, int] | None:
    from choices import REFERRAL_BONUS_RUB

    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT referred_by_user_id FROM users WHERE user_id = ?",
            (referred_user_id,),
        )
        user = await cursor.fetchone()
        if not user or not user["referred_by_user_id"]:
            return None
        referrer_user_id = int(user["referred_by_user_id"])

        cursor = await db.execute(
            "SELECT id FROM referrals WHERE referred_user_id = ?",
            (referred_user_id,),
        )
        if await cursor.fetchone():
            return None

        cursor = await db.execute(
            "SELECT COUNT(*) AS cnt FROM celebrations WHERE user_id = ?",
            (referred_user_id,),
        )
        if int((await cursor.fetchone())["cnt"]) != 1:
            return None

        await db.execute(
            """
            INSERT INTO referrals (referrer_user_id, referred_user_id, bonus_rub)
            VALUES (?, ?, ?)
            """,
            (referrer_user_id, referred_user_id, REFERRAL_BONUS_RUB),
        )
        for uid in (referrer_user_id, referred_user_id):
            await db.execute(
                """
                UPDATE users
                SET referral_credit_rub = COALESCE(referral_credit_rub, 0) + ?
                WHERE user_id = ?
                """,
                (REFERRAL_BONUS_RUB, uid),
            )
        await db.commit()
        return referrer_user_id, REFERRAL_BONUS_RUB


async def consume_referral_credit(user_id: int, amount: int) -> None:
    if amount <= 0:
        return
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "SELECT referral_credit_rub FROM users WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        current = int(row[0] or 0) if row else 0
        await db.execute(
            "UPDATE users SET referral_credit_rub = ? WHERE user_id = ?",
            (max(0, current - amount), user_id),
        )
        await db.commit()


async def update_order_discount(order_id: int, discount_applied: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE orders SET discount_applied = ? WHERE order_id = ?",
            (max(0, discount_applied), order_id),
        )
        await db.commit()


async def add_celebration(
    user_id: int,
    recipient_name: str,
    celebration_date: str,
    style_preference: str,
    taboo_tags: str | None,
    recipient_role: str | None = None,
    recipient_role_custom: str | None = None,
    recipient_fio: str | None = None,
    event_type: str | None = None,
    event_custom: str | None = None,
) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO celebrations
            (user_id, recipient_name, celebration_date, style_preference, taboo_tags,
             recipient_role, recipient_role_custom, recipient_fio, event_type, event_custom)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                recipient_name,
                celebration_date,
                style_preference,
                taboo_tags,
                recipient_role,
                recipient_role_custom,
                recipient_fio,
                event_type,
                event_custom,
            ),
        )
        await db.commit()
        return cursor.lastrowid or 0


async def delete_celebration(celebration_id: int, user_id: int) -> bool:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM celebrations WHERE id = ? AND user_id = ?",
            (celebration_id, user_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_celebration_latest_order(celebration_id: int) -> dict[str, Any] | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT * FROM orders WHERE celebration_id = ?
            ORDER BY order_id DESC LIMIT 1
            """,
            (celebration_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def update_celebration_delivery(
    celebration_id: int,
    user_id: int,
    delivery_street: str,
    delivery_building: str,
    delivery_corps: str | None,
    delivery_apartment: str | None,
    delivery_time: str,
    delivery_comment: str | None = None,
) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            UPDATE celebrations
            SET delivery_street = ?, delivery_building = ?, delivery_corps = ?,
                delivery_apartment = ?, delivery_time = ?, delivery_comment = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                delivery_street,
                delivery_building,
                delivery_corps,
                delivery_apartment,
                delivery_time,
                delivery_comment,
                celebration_id,
                user_id,
            ),
        )
        await db.commit()


async def get_user_celebrations(user_id: int) -> list[dict[str, Any]]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM celebrations WHERE user_id = ? ORDER BY id",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_celebration(celebration_id: int) -> dict[str, Any] | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM celebrations WHERE id = ?",
            (celebration_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_all_celebrations() -> list[dict[str, Any]]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM celebrations")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def create_order(
    user_id: int,
    celebration_id: int,
    budget_selected: int,
) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO orders (user_id, celebration_id, budget_selected, payment_status)
            VALUES (?, ?, ?, 'pending')
            """,
            (user_id, celebration_id, budget_selected),
        )
        await db.commit()
        return cursor.lastrowid or 0


async def update_order_delivery(
    order_id: int,
    delivery_address: str,
    delivery_time: str,
    customer_name: str | None = None,
    customer_phone: str | None = None,
    delivery_comment: str | None = None,
) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            UPDATE orders
            SET delivery_address = ?, delivery_time = ?,
                customer_name = COALESCE(?, customer_name),
                customer_phone = COALESCE(?, customer_phone),
                delivery_comment = COALESCE(?, delivery_comment)
            WHERE order_id = ?
            """,
            (
                delivery_address,
                delivery_time,
                customer_name,
                customer_phone,
                delivery_comment,
                order_id,
            ),
        )
        await db.commit()


async def update_order_payment(
    order_id: int,
    payment_status: str,
    yookassa_payment_id: str | None = None,
) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            UPDATE orders
            SET payment_status = ?, yookassa_payment_id = COALESCE(?, yookassa_payment_id)
            WHERE order_id = ?
            """,
            (payment_status, yookassa_payment_id, order_id),
        )
        await db.commit()


async def get_order(order_id: int) -> dict[str, Any] | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_pending_order_for_celebration(
    user_id: int,
    celebration_id: int,
) -> dict[str, Any] | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT * FROM orders
            WHERE user_id = ? AND celebration_id = ? AND payment_status = 'pending'
            ORDER BY order_id DESC
            LIMIT 1
            """,
            (user_id, celebration_id),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def mark_celebration_reminder_year(celebration_id: int, year: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE celebrations SET reminder_sent_year = ? WHERE id = ?",
            (year, celebration_id),
        )
        await db.commit()


async def mark_celebration_nudge_year(celebration_id: int, year: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE celebrations SET nudge_sent_year = ? WHERE id = ?",
            (year, celebration_id),
        )
        await db.commit()


async def get_unpaid_order_for_celebration_year(
    user_id: int,
    celebration_id: int,
) -> dict[str, Any] | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT * FROM orders
            WHERE user_id = ? AND celebration_id = ?
              AND payment_status = 'pending' AND budget_selected > 0
            ORDER BY order_id DESC
            LIMIT 1
            """,
            (user_id, celebration_id),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

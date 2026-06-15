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
            """
        )
        await db.commit()
    logger.info("Database initialized at %s", DATABASE_PATH)


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


async def add_celebration(
    user_id: int,
    recipient_name: str,
    celebration_date: str,
    style_preference: str,
    taboo_tags: str | None,
) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO celebrations
            (user_id, recipient_name, celebration_date, style_preference, taboo_tags)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, recipient_name, celebration_date, style_preference, taboo_tags),
        )
        await db.commit()
        return cursor.lastrowid or 0


async def get_user_celebrations(user_id: int) -> list[dict[str, Any]]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT id, recipient_name, celebration_date, style_preference, taboo_tags
            FROM celebrations
            WHERE user_id = ?
            ORDER BY id
            """,
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
) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            UPDATE orders
            SET delivery_address = ?, delivery_time = ?
            WHERE order_id = ?
            """,
            (delivery_address, delivery_time, order_id),
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

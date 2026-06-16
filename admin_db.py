"""Синхронный доступ к bot.db для веб-админки (Flask)."""

from __future__ import annotations

import csv
import io
import sqlite3
from typing import Any

from config import DATABASE_PATH


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    return conn


def dashboard_stats() -> dict[str, int]:
    with connect() as db:
        clients = db.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
        celebrations = db.execute("SELECT COUNT(*) AS n FROM celebrations").fetchone()["n"]
        orders = db.execute("SELECT COUNT(*) AS n FROM orders").fetchone()["n"]
        paid = db.execute(
            "SELECT COUNT(*) AS n FROM orders WHERE payment_status = 'paid'"
        ).fetchone()["n"]
        pending = db.execute(
            "SELECT COUNT(*) AS n FROM orders WHERE payment_status = 'pending'"
        ).fetchone()["n"]
        return {
            "clients": clients,
            "celebrations": celebrations,
            "orders": orders,
            "paid": paid,
            "pending": pending,
        }


def list_clients() -> list[dict[str, Any]]:
    with connect() as db:
        rows = db.execute(
            """
            SELECT u.*,
                   (SELECT COUNT(*) FROM celebrations c WHERE c.user_id = u.user_id) AS celebrations_count,
                   (SELECT COUNT(*) FROM orders o WHERE o.user_id = u.user_id) AS orders_count
            FROM users u
            ORDER BY u.created_at DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def list_celebrations() -> list[dict[str, Any]]:
    with connect() as db:
        rows = db.execute(
            """
            SELECT c.*, u.customer_name, u.phone
            FROM celebrations c
            JOIN users u ON u.user_id = c.user_id
            ORDER BY c.id DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def list_orders() -> list[dict[str, Any]]:
    with connect() as db:
        rows = db.execute(
            """
            SELECT o.*, c.recipient_name, c.recipient_fio, c.celebration_date,
                   c.style_preference, u.customer_name AS user_customer_name, u.phone AS user_phone
            FROM orders o
            JOIN celebrations c ON c.id = o.celebration_id
            JOIN users u ON u.user_id = o.user_id
            ORDER BY o.order_id DESC
            """
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["customer_name"] = item.get("customer_name") or item.get("user_customer_name")
            item["phone"] = item.get("user_phone")
            result.append(item)
        return result


def get_order(order_id: int) -> dict[str, Any] | None:
    with connect() as db:
        row = db.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
        return dict(row) if row else None


def get_celebration(celebration_id: int) -> dict[str, Any] | None:
    with connect() as db:
        row = db.execute("SELECT * FROM celebrations WHERE id = ?", (celebration_id,)).fetchone()
        return dict(row) if row else None


def get_user(user_id: int) -> dict[str, Any] | None:
    with connect() as db:
        row = db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def update_order_payment_status(order_id: int, payment_status: str) -> None:
    with connect() as db:
        db.execute(
            "UPDATE orders SET payment_status = ? WHERE order_id = ?",
            (payment_status, order_id),
        )
        db.commit()


def export_csv(table: str) -> str:
    if table == "clients":
        rows = list_clients()
        fields = [
            "user_id",
            "username",
            "customer_name",
            "phone",
            "celebrations_count",
            "orders_count",
            "referral_credit_rub",
            "created_at",
        ]
    elif table == "celebrations":
        rows = list_celebrations()
        fields = [
            "id",
            "user_id",
            "customer_name",
            "phone",
            "recipient_role",
            "recipient_fio",
            "recipient_name",
            "event_type",
            "event_custom",
            "celebration_date",
            "style_preference",
            "taboo_tags",
        ]
    elif table == "orders":
        rows = list_orders()
        fields = [
            "order_id",
            "user_id",
            "customer_name",
            "phone",
            "recipient_name",
            "recipient_fio",
            "celebration_date",
            "budget_selected",
            "payment_status",
            "delivery_address",
            "delivery_time",
            "recipient_contact_phone",
            "delivery_comment",
        ]
    else:
        raise ValueError(f"Unknown table: {table}")

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k, "") for k in fields})
    return buffer.getvalue()

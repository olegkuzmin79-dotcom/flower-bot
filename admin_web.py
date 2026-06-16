"""Веб-админка владельца — читает ту же bot.db, что и Telegram-бот."""

from __future__ import annotations

from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    Response,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

import admin_db
from bot_display import style_label_for
from config import ADMIN_PASSWORD, ADMIN_WEB_ENABLED, DATABASE_PATH, SECRET_KEY
from taboos import format_taboo_list

PAYMENT_STATUSES = (("pending", "Не оплачен"), ("paid", "Оплачен"))
BUDGET_LABELS = {4500: "Эконом", 7500: "Бизнес", 12000: "Премиум"}

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app() -> Flask:
    app = Flask(__name__, template_folder=str(TEMPLATE_DIR), static_folder=str(STATIC_DIR))
    app.secret_key = SECRET_KEY

    def admin_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("admin"):
                return redirect(url_for("admin_login"))
            return view(*args, **kwargs)

        return wrapped

    @app.route("/")
    def index():
        if session.get("admin"):
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("admin_login"))

    @app.route("/health")
    def health():
        return {"ok": True, "database": DATABASE_PATH.exists()}

    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        if request.method == "POST":
            if request.form.get("password") == ADMIN_PASSWORD:
                session["admin"] = True
                return redirect(url_for("admin_dashboard"))
            flash("Неверный пароль", "error")
        return render_template("admin/login.html")

    @app.route("/admin/logout")
    def admin_logout():
        session.pop("admin", None)
        return redirect(url_for("admin_login"))

    @app.route("/admin")
    @admin_required
    def admin_dashboard():
        stats = admin_db.dashboard_stats()
        orders = admin_db.list_orders()[:15]
        return render_template(
            "admin/dashboard.html",
            stats=stats,
            orders=orders,
            database_path=str(DATABASE_PATH),
            budget_labels=BUDGET_LABELS,
            payment_labels=dict(PAYMENT_STATUSES),
        )

    @app.route("/admin/clients")
    @admin_required
    def admin_clients():
        return render_template("admin/clients.html", clients=admin_db.list_clients())

    @app.route("/admin/celebrations")
    @admin_required
    def admin_celebrations():
        items = admin_db.list_celebrations()
        for item in items:
            item["style_label"] = style_label_for(item)
            item["taboo_label"] = format_taboo_list(item.get("taboo_tags"))
        return render_template("admin/celebrations.html", items=items)

    @app.route("/admin/orders")
    @admin_required
    def admin_orders():
        return render_template(
            "admin/orders.html",
            orders=admin_db.list_orders(),
            budget_labels=BUDGET_LABELS,
            payment_labels=dict(PAYMENT_STATUSES),
        )

    @app.route("/admin/orders/<int:order_id>", methods=["GET", "POST"])
    @admin_required
    def admin_order_detail(order_id: int):
        if request.method == "POST":
            status = request.form.get("payment_status")
            if status in {"pending", "paid"}:
                admin_db.update_order_payment_status(order_id, status)
                flash("Статус оплаты обновлён", "ok")
            return redirect(url_for("admin_order_detail", order_id=order_id))

        order = admin_db.get_order(order_id)
        if not order:
            flash("Заказ не найден", "error")
            return redirect(url_for("admin_orders"))
        celebration = admin_db.get_celebration(order["celebration_id"])
        user = admin_db.get_user(order["user_id"])
        return render_template(
            "admin/order_detail.html",
            order=order,
            celebration=celebration,
            user=user,
            budget_labels=BUDGET_LABELS,
            payment_statuses=PAYMENT_STATUSES,
            payment_labels=dict(PAYMENT_STATUSES),
        )

    @app.route("/admin/export/<table>.csv")
    @admin_required
    def admin_export_csv(table: str):
        if table not in {"clients", "celebrations", "orders"}:
            flash("Неизвестный экспорт", "error")
            return redirect(url_for("admin_dashboard"))
        content = admin_db.export_csv(table)
        return Response(
            content,
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={table}.csv"},
        )

    return app


def start_admin_server(port: int) -> None:
    if not ADMIN_WEB_ENABLED:
        return
    import threading

    from werkzeug.serving import make_server

    app = create_app()
    server = make_server("0.0.0.0", port, app, threaded=True)

    thread = threading.Thread(target=server.serve_forever, name="admin-web", daemon=True)
    thread.start()

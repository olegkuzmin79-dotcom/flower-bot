"""Проверка связи с Telegram Bot API. Запуск: python test_connection.py"""
from __future__ import annotations

import asyncio
import socket
import sys

from bot_session import HAPP_SOCKS5, NO_PROXY, SYSTEM_PROXY, create_bot
from config import BOT_TOKEN, DEV_MODE, TELEGRAM_PROXY


def _socks_port_open(host: str = "127.0.0.1", port: int = 10808) -> bool:
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


def _proxy_candidates() -> list[str | None]:
    seen: set[str] = set()
    candidates: list[str | None] = []

    def add(url: str | None) -> None:
        key = url or ""
        if key in seen:
            return
        seen.add(key)
        candidates.append(url)

    if TELEGRAM_PROXY:
        add(TELEGRAM_PROXY)
    add(HAPP_SOCKS5)
    for host in ("127.0.0.1", "192.168.1.9"):
        add(f"socks5://{host}:10808")
    add(SYSTEM_PROXY)
    add(NO_PROXY)
    return candidates


def _label(proxy: str | None) -> str:
    if proxy == SYSTEM_PROXY:
        return "системный прокси Windows"
    if proxy == NO_PROXY:
        return "напрямую (без прокси)"
    return proxy or "?"


async def _try_proxy(proxy: str | None) -> str | None:
    print(f"  -> {_label(proxy)} ... ", end="", flush=True)
    bot = create_bot(proxy=proxy)
    try:
        me = await bot.get_me()
        print("OK")
        return me.username
    except Exception as exc:
        print(f"нет ({type(exc).__name__})")
        return None
    finally:
        await bot.session.close()


async def main() -> None:
    if not BOT_TOKEN:
        print("Ошибка: BOT_TOKEN / BOT_TOKEN_DEV не задан в .env")
        sys.exit(1)

    try:
        import aiohttp_socks  # noqa: F401
    except ImportError:
        print("Сначала: pip install aiohttp-socks")
        sys.exit(1)

    print("Проверяю связь с Telegram.\n")
    if DEV_MODE:
        print("Режим: DEV (токен BOT_TOKEN_DEV)\n")
    else:
        print("Режим: production token (для локалки лучше DEV=1 в .env)\n")

    if _socks_port_open():
        print("Порт SOCKS 127.0.0.1:10808 — открыт (Happ VPN, скорее всего, вкл)\n")
    else:
        print(
            "Порт SOCKS 127.0.0.1:10808 — ЗАКРЫТ.\n"
            "Включи VPN в Happ. В настройках Happ найди SOCKS5 и порт (часто 10808).\n"
            "TUN и системный прокси для Cursor лучше держать ВЫКЛ.\n"
        )

    for proxy in _proxy_candidates():
        username = await _try_proxy(proxy)
        if username:
            print(f"\nOK! Bot @{username}")
            if proxy and proxy not in (NO_PROXY, SYSTEM_PROXY) and proxy != TELEGRAM_PROXY:
                print(f"\nВ .env: TELEGRAM_PROXY={proxy}")
            print("\nЗапускайте: run_local.bat")
            return

    print(
        "\nFAIL — до Telegram API с этого ПК не достучаться.\n\n"
        "Это нормально для РФ без рабочего SOCKS.\n\n"
        "Что работает без VPN:\n"
        "  run_local.bat  (unit-тесты — у тебя уже OK)\n"
        "  python test_validation.py\n\n"
        "Полный бот в Telegram:\n"
        "  git push -> Railway (прод или dev)\n"
        "  либо починить Happ: VPN вкл + SOCKS5 порт открыт\n"
    )
    sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

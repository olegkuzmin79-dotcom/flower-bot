"""Проверка связи с Telegram Bot API. Запуск: python test_connection.py"""
from __future__ import annotations

import asyncio
import sys

from bot_session import HAPP_SOCKS5, SYSTEM_PROXY, create_bot
from config import BOT_TOKEN, DEV_MODE, TELEGRAM_PROXY


def _proxy_candidates() -> list[str | None]:
    seen: set[str] = set()
    candidates: list[str | None] = []

    def add(url: str | None) -> None:
        key = url or ""
        if key in seen:
            return
        seen.add(key)
        candidates.append(url)

    # Happ: «Системный прокси» в доп. настройках
    add(SYSTEM_PROXY)
    add(HAPP_SOCKS5)
    add(TELEGRAM_PROXY)
    for host in ("127.0.0.1", "192.168.1.9"):
        add(f"socks5://{host}:10808")
    add(None)
    return candidates


def _label(proxy: str | None) -> str:
    if proxy == SYSTEM_PROXY:
        return "системный прокси Windows (Happ)"
    return proxy or "(без прокси)"


async def _try_proxy(proxy: str | None) -> str | None:
    print(f"  → {_label(proxy)} ... ", end="", flush=True)
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
        print("Ошибка: BOT_TOKEN не задан в .env")
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
    print("Happ: VPN подключён + Системный прокси ВКЛ")
    print(f"Windows прокси → используем {HAPP_SOCKS5}\n")

    for proxy in _proxy_candidates():
        username = await _try_proxy(proxy)
        if username:
            print(f"\n✅ Работает! Бот @{username}")
            if proxy in (SYSTEM_PROXY, HAPP_SOCKS5):
                print(f"\nВ .env добавьте и сохраните (Ctrl+S):")
                print(f"TELEGRAM_PROXY={HAPP_SOCKS5}")
            elif proxy and proxy != TELEGRAM_PROXY:
                print(f"\nВ .env: TELEGRAM_PROXY={proxy}")
            print("\nЗапускайте: python main.py")
            return

    print(
        "\n❌ Не вышло.\n"
        "Прокси 127.0.0.1:10808 виден, но Telegram API не отвечает.\n"
        "Попробуйте:\n"
        "1. В Happ смените сервер (другая страна)\n"
        "2. Доп. настройки → включите TUN (от имени администратора)\n"
        "3. Переподключите VPN → python test_connection.py\n"
        "\nЕсли снова FAIL — бот на сервере (Railway), без VPN на ПК."
    )
    sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

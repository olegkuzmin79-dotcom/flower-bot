from __future__ import annotations

import logging
import os
import urllib.request

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession

from config import BOT_TOKEN, TELEGRAM_PROXY

logger = logging.getLogger(__name__)

SYSTEM_PROXY = "__system__"
NO_PROXY = "__none__"
HAPP_SOCKS5 = "socks5://127.0.0.1:10808"


def _normalize_proxy(url: str | None) -> str | None:
    """Happ в Windows отдаёт socks4://, а на порту 10808 работает SOCKS5."""
    if not url:
        return None
    if ":10808" in url:
        return HAPP_SOCKS5
    if url.startswith("socks://"):
        return "socks5://" + url[len("socks://") :]
    if url.startswith("socks4://"):
        return "socks5://" + url[len("socks4://") :]
    return url


def _windows_system_proxy() -> str | None:
    try:
        proxies = urllib.request.getproxies()
        raw = proxies.get("https") or proxies.get("http") or proxies.get("socks")
        return _normalize_proxy(raw)
    except Exception:
        logger.exception("Failed to read system proxy")
        return None


def _resolve_proxy() -> str | None:
    if os.getenv("RAILWAY_ENVIRONMENT"):
        return TELEGRAM_PROXY or None
    explicit = TELEGRAM_PROXY or os.getenv("HTTPS_PROXY", "").strip() or os.getenv("HTTP_PROXY", "").strip()
    if explicit:
        return _normalize_proxy(explicit)
    return _windows_system_proxy()


def create_bot(proxy: str | None = None) -> Bot:
    session_kwargs: dict = {
        "timeout": 120,
        "limit": 10,
    }

    if proxy == NO_PROXY:
        resolved = None
    elif proxy == SYSTEM_PROXY:
        resolved = _windows_system_proxy() or HAPP_SOCKS5
    elif proxy is not None:
        resolved = _normalize_proxy(proxy)
    else:
        resolved = _resolve_proxy()

    if resolved:
        session_kwargs["proxy"] = resolved
        logger.info("Telegram API via proxy: %s", resolved)

    session = AiohttpSession(**session_kwargs)
    return Bot(token=BOT_TOKEN, session=session)

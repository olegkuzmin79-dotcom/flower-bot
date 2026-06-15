from __future__ import annotations

import logging
import uuid
from typing import Any

import aiohttp

from config import USE_TEST_PAYMENTS, YOOKASSA_SECRET_KEY, YOOKASSA_SHOP_ID

logger = logging.getLogger(__name__)

YOOKASSA_API = "https://api.yookassa.ru/v3/payments"


async def create_payment(
    amount_rub: int,
    description: str,
    return_url: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    if USE_TEST_PAYMENTS or not (YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY):
        payment_id = f"test_{uuid.uuid4().hex[:12]}"
        logger.info("Test payment created: %s amount=%s", payment_id, amount_rub)
        return {
            "id": payment_id,
            "status": "pending",
            "confirmation_url": None,
            "test_mode": True,
        }

    payload = {
        "amount": {"value": f"{amount_rub:.2f}", "currency": "RUB"},
        "capture": True,
        "confirmation": {"type": "redirect", "return_url": return_url},
        "description": description,
        "metadata": metadata,
        "save_payment_method": True,
    }
    headers = {"Idempotence-Key": str(uuid.uuid4())}
    auth = aiohttp.BasicAuth(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                YOOKASSA_API,
                json=payload,
                headers=headers,
                auth=auth,
            ) as response:
                data = await response.json()
                if response.status >= 400:
                    logger.error("YooKassa error %s: %s", response.status, data)
                    raise RuntimeError(f"YooKassa HTTP {response.status}")
                return {
                    "id": data["id"],
                    "status": data.get("status", "pending"),
                    "confirmation_url": data.get("confirmation", {}).get("confirmation_url"),
                    "test_mode": False,
                }
    except Exception:
        logger.exception("Failed to create YooKassa payment")
        raise

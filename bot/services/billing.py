"""Billing helpers: Crypto Pay (@CryptoBot) client + grant_pro().

Telegram Stars are handled natively by aiogram in handlers/billing.py; this
module owns the crypto HTTP client and the shared Pro-granting logic (with the
anti-fraud velocity guard and admin notification).
"""

from __future__ import annotations

import datetime as dt
import logging

import httpx

from bot.config import Settings
from bot.services.db import Database
from bot.services.quota import Quota

logger = logging.getLogger(__name__)

_CRYPTO_BASE = "https://pay.crypt.bot/api/"


class BillingError(RuntimeError):
    pass


class CryptoPayClient:
    """Minimal async client for the Crypto Pay API."""

    def __init__(self, token: str) -> None:
        self._token = token

    async def create_invoice(
        self, amount: float, asset: str, description: str, payload: str, expires_in: int = 3600
    ) -> dict:
        return await self._call(
            "createInvoice",
            {
                "amount": str(amount),
                "asset": asset,
                "description": description,
                "payload": payload,
                "expires_in": expires_in,
            },
            method="POST",
        )

    async def get_invoice(self, invoice_id: str) -> dict | None:
        result = await self._call("getInvoices", {"invoice_ids": str(invoice_id)}, method="GET")
        items = result.get("items") or []
        return items[0] if items else None

    async def _call(self, method_name: str, params: dict, method: str) -> dict:
        headers = {"Crypto-Pay-API-Token": self._token}
        async with httpx.AsyncClient(base_url=_CRYPTO_BASE, timeout=30.0) as client:
            if method == "GET":
                resp = await client.get(method_name, params=params, headers=headers)
            else:
                resp = await client.post(method_name, json=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            raise BillingError(f"Crypto Pay error on {method_name}: {data}")
        return data["result"]


async def grant_pro(
    *,
    db: Database,
    settings: Settings,
    quota: Quota,
    bot,
    telegram_id: int,
    provider: str,
    amount,
    currency: str,
    charge_id: str | None,
    until: dt.datetime | None = None,
    days: int | None = None,
) -> bool:
    """Grant/extend Pro. Returns True if granted, False if held by the guard.

    Velocity guard: at most MAX_PRO_PURCHASES_PER_DAY grants per user per day;
    beyond that the payment is held and the admin is notified instead.
    """
    if await db.payments_today(telegram_id) >= settings.max_pro_purchases_per_day:
        await _notify_admin(
            bot, settings,
            f"⚠️ HELD: user {telegram_id} exceeded {settings.max_pro_purchases_per_day} "
            f"Pro grants today (provider={provider}). Review for fraud.",
        )
        return False

    user = await quota.ensure_user(telegram_id)
    now = dt.datetime.now(dt.timezone.utc)
    if until is None:
        current = user["pro_until"]
        base = current if current and current > now else now
        until = base + dt.timedelta(days=days or settings.pro_period_days)

    await db.set_pro_until(telegram_id, until)
    await db.payment_insert(telegram_id, provider, amount, currency, charge_id)
    await _notify_admin(
        bot, settings,
        f"💰 Pro granted: user {telegram_id} via {provider} {amount} {currency} "
        f"until {until:%Y-%m-%d}.",
    )
    return True


async def _notify_admin(bot, settings: Settings, text: str) -> None:
    if not settings.admin_user_id:
        return
    try:
        await bot.send_message(settings.admin_user_id, text)
    except Exception:  # noqa: BLE001 - admin notification must never break a flow
        logger.warning("Failed to notify admin")

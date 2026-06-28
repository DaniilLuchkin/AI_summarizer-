"""Billing helpers: shared Pro-granting logic (Telegram Stars only).

Telegram Stars are handled natively by aiogram in handlers/billing.py; this
module owns the Pro grant (Pro window + monthly credits + ledgered payment),
with the anti-fraud velocity guard and admin notification.
"""

from __future__ import annotations

import datetime as dt
import logging

from bot.config import Settings
from bot.services.credits import CreditService
from bot.services.db import Database
from bot.services.quota import Quota

logger = logging.getLogger(__name__)


class BillingError(RuntimeError):
    pass


async def grant_pro(
    *,
    db: Database,
    settings: Settings,
    quota: Quota,
    credits: CreditService,
    bot,
    telegram_id: int,
    amount,
    charge_id: str | None,
    until: dt.datetime | None = None,
    days: int | None = None,
) -> bool:
    """Grant/extend Pro and add the monthly credit grant. False if held by guard.

    Velocity guard: at most MAX_PRO_PURCHASES_PER_DAY grants per user per day;
    beyond that the payment is held and the admin is notified instead.
    """
    if await db.payments_today(telegram_id) >= settings.max_pro_purchases_per_day:
        await _notify_admin(
            bot, settings,
            f"⚠️ HELD: user {telegram_id} exceeded {settings.max_pro_purchases_per_day} "
            f"Pro grants today. Review for fraud.",
        )
        return False

    user = await quota.ensure_user(telegram_id)
    now = dt.datetime.now(dt.timezone.utc)
    if until is None:
        current = user["pro_until"]
        base = current if current and current > now else now
        until = base + dt.timedelta(days=days or settings.pro_period_days)

    await db.set_pro_until(telegram_id, until)
    await credits.grant_pro_monthly(telegram_id)  # PRO_MONTHLY_CREDITS each cycle
    await db.payment_insert(telegram_id, "stars", amount, "XTR", charge_id)
    await _notify_admin(
        bot, settings,
        f"💰 Pro granted: user {telegram_id} via Stars {amount} XTR "
        f"(+{settings.pro_monthly_credits} credits) until {until:%Y-%m-%d}.",
    )
    return True


async def _notify_admin(bot, settings: Settings, text: str) -> None:
    if not settings.admin_user_id:
        return
    try:
        await bot.send_message(settings.admin_user_id, text)
    except Exception:  # noqa: BLE001 - admin notification must never break a flow
        logger.warning("Failed to notify admin")

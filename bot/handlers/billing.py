"""Purchases — Telegram Stars only: Pro subscription + one-off credit packs.

1 ⭐ = 1 credit. Pro is a native 30-day Stars subscription that grants
PRO_MONTHLY_CREDITS each cycle and gives PRO_CREDIT_DISCOUNT off credit packs.
Every grant is recorded in `payments` and logged to the credit ledger.
"""

from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.methods import SendInvoice
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)

from bot.config import Settings
from bot.handlers.run import BUY_CB, UPGRADE_CB, build_upgrade_keyboard
from bot.services.billing import grant_pro
from bot.services.credits import fmt
from bot.texts import resolve_lang, t

logger = logging.getLogger(__name__)

# Telegram only supports a fixed 30-day Stars subscription period.
_STARS_SUB_PERIOD = 2592000


class _SendInvoiceWithSubscription(SendInvoice):
    """aiogram (3.x) doesn't type `subscription_period`; declare it ourselves."""

    subscription_period: int | None = None


def _pack_stars(credits: int, pro: bool, s: Settings) -> int:
    """Stars price for a credit pack (Pro gets PRO_CREDIT_DISCOUNT off)."""
    if pro:
        return max(1, round(credits * (1 - s.pro_credit_discount)))
    return credits


def _render_plans(s: Settings, lang: str) -> str:
    """Free (credits) → Pro (value math) → BYO, built from current config."""
    free = t("plans_free_block", lang).format(
        signup=s.signup_bonus_credits, daily=s.daily_free_credits,
    )
    pro = t("plans_pro_block", lang).format(
        stars=s.pro_price_stars,
        pro_credits=s.pro_monthly_credits,
        discount=int(s.pro_credit_discount * 100),
    )
    return "\n\n".join([t("plans_header", lang), free, pro, t("plans_byo_line", lang)])


def build_router(ctx) -> Router:
    router = Router(name="billing")
    s = ctx.settings

    def _lang(message: Message) -> str:
        return ctx.store.get_lang(message.chat.id) or resolve_lang(
            message.from_user.language_code if message.from_user else None
        )

    def _purchase_keyboard(lang: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t("btn_pay_stars", lang), callback_data="buy:stars")],
            [InlineKeyboardButton(text=t("btn_buy_credits", lang), callback_data=BUY_CB)],
        ])

    async def show_purchase_options(message: Message, lang: str) -> None:
        """'Why Pro' value math + how-to-pay buttons (used by /pro and Upgrade)."""
        text = t("pro_value_math", lang).format(
            stars=s.pro_price_stars,
            pro_credits=s.pro_monthly_credits,
            discount=int(s.pro_credit_discount * 100),
        )
        await message.answer(text, reply_markup=_purchase_keyboard(lang))

    async def _credit_packs_kb(uid: int, lang: str) -> InlineKeyboardMarkup:
        user = await ctx.quota.ensure_user(uid)
        pro = ctx.quota.is_pro(user)
        rows = []
        for n in s.credit_pack_sizes:
            stars = _pack_stars(n, pro, s)
            rows.append([InlineKeyboardButton(
                text=t("pack_label", lang).format(credits=n, stars=stars),
                callback_data=f"pack:{n}",
            )])
        return InlineKeyboardMarkup(inline_keyboard=rows)

    # --- /pro -----------------------------------------------------------
    @router.message(Command("pro"))
    async def cmd_pro(message: Message, state: FSMContext) -> None:
        await state.clear()
        await ctx.quota.ensure_user(message.from_user.id)
        await show_purchase_options(message, _lang(message))

    @router.callback_query(F.data == UPGRADE_CB)
    async def on_upgrade(callback: CallbackQuery) -> None:
        await callback.answer()
        await ctx.quota.ensure_user(callback.from_user.id)
        await show_purchase_options(callback.message, _lang(callback.message))

    # --- Buy credits (packs) --------------------------------------------
    @router.callback_query(F.data == BUY_CB)
    async def on_buy(callback: CallbackQuery) -> None:
        await callback.answer()
        lang = _lang(callback.message)
        await ctx.quota.ensure_user(callback.from_user.id)
        kb = await _credit_packs_kb(callback.from_user.id, lang)
        await callback.message.answer(t("buy_credits_header", lang), reply_markup=kb)

    @router.callback_query(F.data.startswith("pack:"))
    async def buy_pack(callback: CallbackQuery, bot: Bot) -> None:
        await callback.answer()
        lang = _lang(callback.message)
        credits = int(callback.data.split(":", 1)[1])
        user = await ctx.quota.ensure_user(callback.from_user.id)
        stars = _pack_stars(credits, ctx.quota.is_pro(user), s)
        await bot(SendInvoice(
            chat_id=callback.message.chat.id,
            title=t("pack_invoice_title", lang).format(credits=credits),
            description=t("pack_invoice_desc", lang).format(credits=credits),
            payload=f"pack:{credits}",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label=f"{credits} credits", amount=stars)],
        ))

    # --- Pro subscription (Stars) ---------------------------------------
    @router.callback_query(F.data == "buy:stars")
    async def buy_stars(callback: CallbackQuery, bot: Bot) -> None:
        await callback.answer()
        lang = _lang(callback.message)
        await bot(_SendInvoiceWithSubscription(
            chat_id=callback.message.chat.id,
            title=t("invoice_title", lang),
            description=t("invoice_description", lang),
            payload="pro_sub",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label="Forwardly Pro", amount=s.pro_price_stars)],
            subscription_period=_STARS_SUB_PERIOD,
        ))

    @router.pre_checkout_query()
    async def pre_checkout(query: PreCheckoutQuery) -> None:
        await query.answer(ok=True)

    @router.message(F.successful_payment)
    async def on_successful_payment(message: Message, bot: Bot) -> None:
        sp = message.successful_payment
        lang = _lang(message)
        payload = sp.invoice_payload or ""

        if payload.startswith("pack:"):
            credits = int(payload.split(":", 1)[1])
            await ctx.credits.grant_pack(message.from_user.id, credits)
            await ctx.db.payment_insert(
                message.from_user.id, "stars", sp.total_amount, "XTR",
                sp.telegram_payment_charge_id,
            )
            await message.answer(t("credits_added", lang).format(credits=fmt(credits * 10)))
            return

        granted = await grant_pro(
            db=ctx.db, settings=s, quota=ctx.quota, credits=ctx.credits, bot=bot,
            telegram_id=message.from_user.id,
            amount=sp.total_amount,
            charge_id=sp.telegram_payment_charge_id,
            until=sp.subscription_expiration_date,
            days=s.pro_period_days,
        )
        await message.answer(t("payment_success" if granted else "payment_held", lang))

    # --- /plans ---------------------------------------------------------
    @router.message(Command("plans"))
    async def cmd_plans(message: Message, state: FSMContext) -> None:
        await state.clear()
        user = await ctx.quota.ensure_user(message.from_user.id)
        lang = _lang(message)
        text = _render_plans(s, lang)
        if ctx.quota.is_pro(user):
            text += "\n\n" + t("plans_pro_active", lang).format(
                date=user["pro_until"].strftime("%Y-%m-%d")
            )
            await message.answer(text)
        elif ctx.quota.has_byo(user):
            await message.answer(text)
        else:
            await message.answer(text, reply_markup=build_upgrade_keyboard(lang))

    return router

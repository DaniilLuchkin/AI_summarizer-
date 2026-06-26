"""Pro purchase flow: /pro, Telegram Stars, and Crypto Pay.

Stars use a native 30-day subscription (the only period Telegram supports).
Crypto uses @CryptoBot invoices confirmed by an "I've paid — check" button.
Both record a row in `payments`, notify the admin, and respect the velocity guard.
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

from bot.handlers.run import UPGRADE_CB, build_upgrade_keyboard
from bot.runtime import AppContext
from bot.services.billing import CryptoPayClient, grant_pro
from bot.config import Settings
from bot.texts import resolve_lang, t

logger = logging.getLogger(__name__)


def _render_plans(s: Settings, lang: str) -> str:
    """Build the Free vs Pro comparison entirely from current config values."""
    free = t("plans_free_block", lang).format(
        signup_audio_min=s.free_signup_audio_sec // 60,
        signup_photos=s.free_signup_photos,
        daily_audio_min=s.free_daily_audio_sec // 60,
        daily_photos=s.free_daily_photos,
        daily_llm=s.free_daily_llm_calls,
        saved_prompts=s.free_saved_prompts,
    )
    pro = t("plans_pro_block", lang).format(
        pro_audio_min=s.pro_daily_audio_sec // 60,
        pro_photos=s.pro_daily_photos,
        pro_llm=s.pro_daily_llm_calls,
        pro_images=s.pro_daily_images,
        pro_pptx=s.pro_daily_pptx,
        pro_model=s.text_model_pro,
        pro_context=s.max_context_chars_pro,
    )
    price = t("plans_price_line", lang).format(stars=s.pro_price_stars, usdt=s.pro_price_usdt)
    return "\n\n".join(
        [t("plans_header", lang), free, pro, t("plans_byo_line", lang), price]
    )

# Telegram only supports a fixed 30-day Stars subscription period.
_STARS_SUB_PERIOD = 2592000


class _SendInvoiceWithSubscription(SendInvoice):
    """aiogram (3.x) doesn't type `subscription_period`; declare it ourselves."""

    subscription_period: int | None = None


def build_router(ctx: AppContext) -> Router:
    router = Router(name="billing")
    s = ctx.settings

    def _lang(message: Message) -> str:
        return ctx.store.get_lang(message.chat.id) or resolve_lang(
            message.from_user.language_code if message.from_user else None
        )

    def _purchase_keyboard(lang: str) -> InlineKeyboardMarkup:
        """Stars (+ crypto if enabled) purchase buttons."""
        rows = [[InlineKeyboardButton(text=t("btn_pay_stars", lang), callback_data="buy:stars")]]
        if s.crypto_pay_api_token:
            rows.append(
                [InlineKeyboardButton(text=t("btn_pay_crypto", lang), callback_data="buy:crypto")]
            )
        return InlineKeyboardMarkup(inline_keyboard=rows)

    async def show_purchase_options(message: Message, lang: str) -> None:
        """Shared 'choose how to pay' screen, used by /pro and the upgrade button."""
        await message.answer(
            t("pro_benefits", lang).format(stars=s.pro_price_stars, usdt=s.pro_price_usdt),
            reply_markup=_purchase_keyboard(lang),
        )

    # --- /pro -----------------------------------------------------------
    @router.message(Command("pro"))
    async def cmd_pro(message: Message, state: FSMContext) -> None:
        await state.clear()
        await ctx.quota.ensure_user(message.from_user.id)
        await show_purchase_options(message, _lang(message))

    # --- One-tap upgrade button (from /plans and every paywall) ---------
    @router.callback_query(F.data == UPGRADE_CB)
    async def on_upgrade(callback: CallbackQuery) -> None:
        await callback.answer()
        await ctx.quota.ensure_user(callback.from_user.id)
        await show_purchase_options(callback.message, _lang(callback.message))

    # --- /plans: tariff comparison, generated from config ---------------
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
            await message.answer(text)  # BYO already unlocks everything
        else:
            await message.answer(text, reply_markup=build_upgrade_keyboard(lang))

    # --- Telegram Stars --------------------------------------------------
    @router.callback_query(F.data == "buy:stars")
    async def buy_stars(callback: CallbackQuery, bot: Bot) -> None:
        await callback.answer()
        # Native 30-day Stars subscription (provider_token empty for XTR).
        await bot(
            _SendInvoiceWithSubscription(
                chat_id=callback.message.chat.id,
                title="Forwardly Pro",
                description="Pro for 30 days: images, presentations, bigger context.",
                payload="pro_sub",
                provider_token="",
                currency="XTR",
                prices=[LabeledPrice(label="Forwardly Pro", amount=s.pro_price_stars)],
                subscription_period=_STARS_SUB_PERIOD,
            )
        )

    @router.pre_checkout_query()
    async def pre_checkout(query: PreCheckoutQuery) -> None:
        await query.answer(ok=True)

    @router.message(F.successful_payment)
    async def on_successful_payment(message: Message, bot: Bot) -> None:
        sp = message.successful_payment
        lang = _lang(message)
        until = sp.subscription_expiration_date  # datetime or None (aiogram parses it)
        granted = await grant_pro(
            db=ctx.db, settings=s, quota=ctx.quota, bot=bot,
            telegram_id=message.from_user.id,
            provider="stars",
            amount=sp.total_amount,
            currency="XTR",
            charge_id=sp.telegram_payment_charge_id,
            until=until,
            days=s.pro_period_days,
        )
        await message.answer(t("payment_success" if granted else "payment_held", lang))

    # --- Crypto Pay ------------------------------------------------------
    @router.callback_query(F.data == "buy:crypto")
    async def buy_crypto(callback: CallbackQuery) -> None:
        await callback.answer()
        lang = _lang(callback.message)
        try:
            client = CryptoPayClient(s.crypto_pay_api_token)
            invoice = await client.create_invoice(
                s.pro_price_usdt, "USDT", "Forwardly Pro 30 days", str(callback.from_user.id)
            )
        except Exception:  # noqa: BLE001
            logger.exception("Crypto invoice creation failed")
            await callback.message.answer(t("generic_error", lang))
            return
        pay_url = (
            invoice.get("bot_invoice_url")
            or invoice.get("mini_app_invoice_url")
            or invoice.get("pay_url")
        )
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=f"💳 {s.pro_price_usdt} USDT", url=pay_url)],
                [
                    InlineKeyboardButton(
                        text=t("btn_paid_check", lang),
                        callback_data=f"cpay:{invoice['invoice_id']}",
                    )
                ],
            ]
        )
        await callback.message.answer(t("pro_benefits", lang).format(
            stars=s.pro_price_stars, usdt=s.pro_price_usdt), reply_markup=keyboard)

    @router.callback_query(F.data.startswith("cpay:"))
    async def crypto_check(callback: CallbackQuery, bot: Bot) -> None:
        await callback.answer()
        invoice_id = callback.data.split(":", 1)[1]
        lang = _lang(callback.message)
        try:
            client = CryptoPayClient(s.crypto_pay_api_token)
            invoice = await client.get_invoice(invoice_id)
        except Exception:  # noqa: BLE001
            logger.exception("Crypto invoice check failed")
            await callback.message.answer(t("generic_error", lang))
            return

        if invoice and invoice.get("status") == "paid":
            granted = await grant_pro(
                db=ctx.db, settings=s, quota=ctx.quota, bot=bot,
                telegram_id=callback.from_user.id,
                provider="crypto",
                amount=s.pro_price_usdt,
                currency="USDT",
                charge_id=str(invoice_id),
                days=s.pro_period_days,
            )
            await callback.message.answer(t("payment_success" if granted else "payment_held", lang))
        else:
            await callback.message.answer(t("crypto_not_paid", lang))

    return router

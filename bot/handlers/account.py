"""Account & data commands: /setkey /removekey /prompts /usage /privacy
/forgetme /invite, plus the saved-prompt callbacks.

These integrate with the DB/quota layer. Access control is the global
middleware; language comes from the in-memory store (override-aware).
"""

from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from bot.handlers import execute
from bot.handlers.run import build_upgrade_keyboard
from bot.runtime import AppContext
from bot.texts import resolve_lang, t

logger = logging.getLogger(__name__)

_TITLE_LEN = 40


def build_router(ctx: AppContext) -> Router:
    router = Router(name="account")
    s = ctx.settings

    def _lang(message: Message) -> str:
        return ctx.store.get_lang(message.chat.id) or resolve_lang(
            message.from_user.language_code if message.from_user else None
        )

    async def _invite_link(bot: Bot, code: str) -> str:
        me = await bot.get_me()
        return f"https://t.me/{me.username}?start=ref_{code}"

    # --- BYO key ---------------------------------------------------------
    @router.message(Command("setkey"))
    async def cmd_setkey(message: Message, command: CommandObject, bot: Bot) -> None:
        lang = _lang(message)
        key = (command.args or "").strip()
        # Delete the message so the secret doesn't linger in the chat.
        try:
            await message.delete()
        except Exception:  # noqa: BLE001
            pass
        if not key or not ctx.quota.fernet_available:
            await bot.send_message(message.chat.id, t("key_invalid", lang))
            return
        if not await ctx.orclient.validate_key(key):
            await bot.send_message(message.chat.id, t("key_invalid", lang))
            return
        await ctx.quota.ensure_user(message.from_user.id)
        await ctx.db.set_byo_key(message.from_user.id, ctx.quota.encrypt_key(key))
        await bot.send_message(message.chat.id, t("key_saved", lang))

    @router.message(Command("removekey"))
    async def cmd_removekey(message: Message) -> None:
        await ctx.quota.ensure_user(message.from_user.id)
        await ctx.db.set_byo_key(message.from_user.id, None)
        await message.answer(t("key_removed", _lang(message)))

    # --- Usage / privacy / invite ---------------------------------------
    @router.message(Command("usage"))
    async def cmd_usage(message: Message, bot: Bot) -> None:
        lang = _lang(message)
        r = await ctx.quota.remaining(message.from_user.id)
        plan = (
            t("plan_pro", lang).format(date=r["pro_until"].strftime("%Y-%m-%d"))
            if r["pro"]
            else (t("byo_active", lang) if r["byo"] else t("plan_free", lang))
        )
        invite = await _invite_link(bot, r["referral_code"])
        await message.answer(
            t("usage_report", lang).format(
                plan=plan,
                audio_min=r["audio_sec"] // 60,
                photos=r["photos"],
                llm=r["llm_calls"],
                images=r["images"],
                pptx=r["pptx"],
                bonus_audio_min=r["bonus_audio_sec"] // 60,
                bonus_photos=r["bonus_photos"],
                invite=invite,
            )
        )

    @router.message(Command("invite"))
    async def cmd_invite(message: Message, bot: Bot) -> None:
        lang = _lang(message)
        user = await ctx.quota.ensure_user(message.from_user.id)
        link = await _invite_link(bot, user["referral_code"])
        await message.answer(
            t("invite_text", lang).format(
                link=link, audio_min=s.referral_bonus_audio_sec // 60,
                photos=s.referral_bonus_photos,
            )
        )

    @router.message(Command("privacy"))
    async def cmd_privacy(message: Message) -> None:
        await message.answer(t("privacy_text", _lang(message)))

    # --- Forget me (delete data) ----------------------------------------
    @router.message(Command("forgetme"))
    async def cmd_forgetme(message: Message) -> None:
        lang = _lang(message)
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅", callback_data="forget:yes"),
                    InlineKeyboardButton(text="❌", callback_data="forget:no"),
                ]
            ]
        )
        await message.answer(t("forgetme_confirm", lang), reply_markup=keyboard)

    @router.callback_query(F.data.startswith("forget:"))
    async def forget_cb(callback: CallbackQuery) -> None:
        await callback.answer()
        lang = _lang(callback.message)
        if callback.data == "forget:yes":
            await ctx.db.delete_user(callback.from_user.id)
            ctx.store.clear_session(callback.message.chat.id)
            await callback.message.edit_text(t("forgetme_done", lang))
        else:
            await callback.message.edit_text("❌")

    # --- Saved prompts ---------------------------------------------------
    @router.callback_query(F.data == "save_prompt")
    async def save_prompt(callback: CallbackQuery) -> None:
        await callback.answer()
        lang = _lang(callback.message)
        chat_state = ctx.store.get(callback.message.chat.id)
        body = chat_state.last_custom_prompt if chat_state else None
        if not body:
            return
        user = await ctx.quota.ensure_user(callback.from_user.id)
        unlimited = ctx.quota.is_pro(user) or ctx.quota.has_byo(user)
        if not unlimited:
            count = await ctx.db.prompts_count(callback.from_user.id)
            if count >= s.free_saved_prompts:
                await callback.message.answer(
                    t("prompts_limit", lang).format(limit=s.free_saved_prompts),
                    reply_markup=build_upgrade_keyboard(lang),
                )
                return
        await ctx.db.prompt_add(callback.from_user.id, body[:_TITLE_LEN], body)
        await callback.message.answer(t("prompt_saved", lang))

    @router.message(Command("prompts"))
    async def cmd_prompts(message: Message) -> None:
        lang = _lang(message)
        rows = await ctx.db.prompts_list(message.from_user.id)
        if not rows:
            await message.answer(t("prompts_empty", lang))
            return
        keyboard = []
        for row in rows:
            keyboard.append(
                [
                    InlineKeyboardButton(text=row["title"], callback_data=f"prompt:run:{row['id']}"),
                    InlineKeyboardButton(text="🗑", callback_data=f"prompt:del:{row['id']}"),
                ]
            )
        await message.answer(
            t("prompts_pick", lang), reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )

    @router.callback_query(F.data.startswith("prompt:del:"))
    async def prompt_delete(callback: CallbackQuery) -> None:
        await callback.answer()
        prompt_id = int(callback.data.rsplit(":", 1)[1])
        await ctx.db.prompt_delete(prompt_id, callback.from_user.id)
        try:
            await callback.message.delete()
        except Exception:  # noqa: BLE001
            pass

    @router.callback_query(F.data.startswith("prompt:run:"))
    async def prompt_run(callback: CallbackQuery, bot: Bot) -> None:
        await callback.answer()
        lang = _lang(callback.message)
        prompt_id = int(callback.data.rsplit(":", 1)[1])
        row = await ctx.db.prompt_get(prompt_id, callback.from_user.id)
        if row is None:
            return
        chat_state = ctx.store.get(callback.message.chat.id)
        if chat_state is None or not chat_state.has_active_batch:
            await callback.message.answer(t("no_active_batch", lang))
            return
        await execute.run_staged(
            ctx, callback.message, bot, lang, callback.from_user.id, "custom",
            source_message=None, preset_instruction=row["body"],
        )

    return router

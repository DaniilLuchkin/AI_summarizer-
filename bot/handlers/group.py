"""Group-chat mode: passively buffer messages, then /summary /ask /actions /clear.

Requires the bot's Telegram privacy mode to be OFF (see README) — otherwise it
only receives commands and can't buffer the conversation. All handlers filter
strictly on group/supergroup chats so DM (forwarded-batch) behavior is untouched.

The buffer is in-memory only (services/group_buffer.py); nothing about group
content is written to Postgres. Group LLM commands consume the invoker's
`llm_calls` quota and are additionally rate-limited by a per-group cooldown.
"""

from __future__ import annotations

import logging
import time

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import ChatMemberUpdated, Message

from bot.output import send_result
from bot.prompts import GROUP_ACTIONS_SYSTEM, GROUP_ASK_SYSTEM, GROUP_SUMMARY_SYSTEM
from bot.runtime import AppContext
from bot.services.group_buffer import BufferItem
from bot.services.openrouter import OpenRouterError
from bot.texts import resolve_lang, t

logger = logging.getLogger(__name__)

_GROUP_TYPES = {"group", "supergroup"}
_ADMIN_STATUSES = {"creator", "administrator"}
_JOINED_STATUSES = {"member", "administrator", "restricted"}
_LEFT_STATUSES = {"left", "kicked"}


def _format_items(items: list[BufferItem]) -> str:
    """Render buffered messages as 'Name: text' lines for the LLM."""
    return "\n".join(f"{i.user_name}: {i.text}" for i in items)


def build_router(ctx: AppContext) -> Router:
    router = Router(name="group")
    s = ctx.settings
    group_filter = F.chat.type.in_(_GROUP_TYPES)
    # Per-group cooldown timestamps (in-memory; spam guard on top of quota).
    last_run: dict[int, float] = {}

    def _lang(message: Message) -> str:
        return resolve_lang(message.from_user.language_code if message.from_user else None)

    async def _run_llm(message: Message, invoker_id: int, lang: str, system: str, content: str):
        """Call the text model with the invoker's BYO key / Pro model and post it."""
        api_key = await ctx.quota.api_key_for(invoker_id)
        model = await ctx.quota.model_for(invoker_id)
        try:
            answer = await ctx.orclient.chat(
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": content},
                ],
                model=model,
                api_key=api_key,
            )
        except OpenRouterError:
            logger.exception("Group LLM call failed")
            await message.reply(t("llm_error", lang))
            return
        except Exception:  # noqa: BLE001
            logger.exception("Unexpected group LLM error")
            await message.reply(t("generic_error", lang))
            return
        await send_result(message, answer, lang)

    def _on_cooldown(chat_id: int) -> bool:
        return time.time() - last_run.get(chat_id, 0.0) < s.group_cooldown_sec

    # --- Bot added to a group -> one-time intro -------------------------
    @router.my_chat_member()
    async def on_my_chat_member(event: ChatMemberUpdated, bot: Bot) -> None:
        if event.chat.type not in _GROUP_TYPES:
            return
        old = event.old_chat_member.status
        new = event.new_chat_member.status
        if old not in _LEFT_STATUSES or new not in _JOINED_STATUSES:
            return  # not a fresh join (e.g. just a promotion) -> no intro
        lang = resolve_lang(event.from_user.language_code if event.from_user else None)
        try:
            await bot.send_message(event.chat.id, t("group_intro", lang))
        except Exception:  # noqa: BLE001
            logger.warning("Failed to post group intro")

    # --- /summary [N] ----------------------------------------------------
    @router.message(group_filter, Command("summary"))
    async def cmd_summary(message: Message, command: CommandObject) -> None:
        lang = _lang(message)
        invoker = message.from_user.id
        user = await ctx.quota.ensure_user(invoker)
        chat_id = message.chat.id

        if _on_cooldown(chat_id):
            await message.reply(t("group_cooldown", lang))
            return

        pro = ctx.quota.is_pro(user) or ctx.quota.has_byo(user)
        window = s.group_window_pro if pro else s.group_window_free
        n = s.group_summary_default
        if command.args:
            try:
                n = int(command.args.split()[0])
            except ValueError:
                pass
        n = max(1, min(n, window))

        # Reply-to a buffered message -> summarize from there to now.
        if message.reply_to_message:
            items = ctx.group_buffer.get_since(chat_id, message.reply_to_message.message_id)
            items = items[-window:]
        else:
            items = ctx.group_buffer.get_recent(chat_id, n)

        if not items:
            await message.reply(t("group_summary_empty", lang))
            return

        ok, _ = await ctx.quota.consume_llm_call(invoker)
        if not ok:
            await message.reply(t("limit_llm", lang))
            return
        last_run[chat_id] = time.time()
        await _run_llm(message, invoker, lang, GROUP_SUMMARY_SYSTEM, _format_items(items))

    # --- /ask <question>  (Pro / BYO only) ------------------------------
    @router.message(group_filter, Command("ask"))
    async def cmd_ask(message: Message, command: CommandObject) -> None:
        lang = _lang(message)
        invoker = message.from_user.id
        user = await ctx.quota.ensure_user(invoker)
        if not (ctx.quota.is_pro(user) or ctx.quota.has_byo(user)):
            await message.reply(t("paywall_generic", lang))
            return
        question = (command.args or "").strip()
        if not question:
            await message.reply(t("group_ask_usage", lang))
            return
        if _on_cooldown(message.chat.id):
            await message.reply(t("group_cooldown", lang))
            return
        items = ctx.group_buffer.get_recent(message.chat.id, s.group_window_pro)
        if not items:
            await message.reply(t("group_summary_empty", lang))
            return
        ok, _ = await ctx.quota.consume_llm_call(invoker)
        if not ok:
            await message.reply(t("limit_llm", lang))
            return
        last_run[message.chat.id] = time.time()
        content = f"{_format_items(items)}\n\nQuestion: {question}"
        await _run_llm(message, invoker, lang, GROUP_ASK_SYSTEM, content)

    # --- /actions  (Pro / BYO only) -------------------------------------
    @router.message(group_filter, Command("actions"))
    async def cmd_actions(message: Message) -> None:
        lang = _lang(message)
        invoker = message.from_user.id
        user = await ctx.quota.ensure_user(invoker)
        if not (ctx.quota.is_pro(user) or ctx.quota.has_byo(user)):
            await message.reply(t("paywall_generic", lang))
            return
        if _on_cooldown(message.chat.id):
            await message.reply(t("group_cooldown", lang))
            return
        items = ctx.group_buffer.get_recent(message.chat.id, s.group_window_pro)
        if not items:
            await message.reply(t("group_summary_empty", lang))
            return
        ok, _ = await ctx.quota.consume_llm_call(invoker)
        if not ok:
            await message.reply(t("limit_llm", lang))
            return
        last_run[message.chat.id] = time.time()
        await _run_llm(message, invoker, lang, GROUP_ACTIONS_SYSTEM, _format_items(items))

    # --- /clear  (admins only) ------------------------------------------
    @router.message(group_filter, Command("clear"))
    async def cmd_clear(message: Message, bot: Bot) -> None:
        lang = _lang(message)
        member = await bot.get_chat_member(message.chat.id, message.from_user.id)
        if member.status in _ADMIN_STATUSES:
            ctx.group_buffer.clear(message.chat.id)
            await message.reply(t("group_cleared", lang))
        else:
            await message.reply(t("group_admins_only", lang))

    # --- Passive buffering (must be the LAST message handler here) -------
    @router.message(group_filter, F.text | F.caption)
    async def buffer_message(message: Message) -> None:
        if message.from_user is None or message.from_user.is_bot:
            return
        text = message.text or message.caption
        if not text or text.startswith("/"):
            return  # commands/empties aren't conversation context
        ctx.group_buffer.add_message(
            message.chat.id, message.message_id, message.from_user.full_name, text, time.time()
        )

    return router

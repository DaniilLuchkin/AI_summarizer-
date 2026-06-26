"""/models — per-task model selection for BYO-key users (private chat only).

Shows the four slots (text / vision / transcription / image), lets a BYO user
pick from a live, slot-filtered shortlist or enter a custom slug. Non-BYO users
are told it unlocks with /setkey and keep the global defaults.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from bot.runtime import AppContext
from bot.services.models import SLOTS
from bot.texts import resolve_lang, t

logger = logging.getLogger(__name__)

_SLOT_LABEL = {
    "text": "models_slot_text",
    "vision": "models_slot_vision",
    "transcribe": "models_slot_transcribe",
    "image": "models_slot_image",
}
_SLOT_EMOJI = {"text": "📝", "vision": "🖼", "transcribe": "🎙", "image": "🎨"}


class ModelStates(StatesGroup):
    awaiting_slug = State()  # data: {"slot": <slot>}


def build_router(ctx: AppContext) -> Router:
    router = Router(name="models")
    private = F.chat.type == "private"
    # Ephemeral UI state: chat_id -> (slot, [slug, ...]) for the shown picker.
    picker: dict[int, tuple[str, list[str]]] = {}

    def _lang(message: Message) -> str:
        return ctx.store.get_lang(message.chat.id) or resolve_lang(
            message.from_user.language_code if message.from_user else None
        )

    # --- /models ---------------------------------------------------------
    @router.message(Command("models"), private)
    async def cmd_models(message: Message, state: FSMContext) -> None:
        await state.clear()
        lang = _lang(message)
        uid = message.from_user.id
        await ctx.quota.ensure_user(uid)
        if await ctx.quota.api_key_for(uid) is None:
            await message.answer(t("models_byo_only", lang))
            return
        await _show_overview(message, uid, lang)

    async def _show_overview(message: Message, uid: int, lang: str) -> None:
        prefs = await ctx.models.get_user_models(uid)
        lines = [t("models_header", lang)]
        rows: list[list[InlineKeyboardButton]] = []
        for slot in SLOTS:
            override = prefs.get(slot)
            shown = override or f"{t('models_default', lang)}: {await ctx.models.resolve(uid, slot)}"
            lines.append(f"{_SLOT_EMOJI[slot]} {t(_SLOT_LABEL[slot], lang)}: {shown}")
            rows.append(
                [InlineKeyboardButton(
                    text=f"{_SLOT_EMOJI[slot]} {t('btn_change', lang)}",
                    callback_data=f"mdl:change:{slot}",
                )]
            )
        rows.append([InlineKeyboardButton(text=t("btn_reset_all", lang), callback_data="mdl:resetall")])
        await message.answer("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

    # --- Change a slot: show the shortlist -------------------------------
    @router.callback_query(F.data.startswith("mdl:change:"))
    async def on_change(callback: CallbackQuery) -> None:
        await callback.answer()
        slot = callback.data.split(":")[2]
        uid = callback.from_user.id
        lang = _lang(callback.message)
        key = await ctx.quota.api_key_for(uid)
        if key is None:
            await callback.message.answer(t("models_byo_only", lang))
            return
        shortlist = await ctx.models.shortlist_for(slot, key)
        picker[callback.message.chat.id] = (slot, [m["id"] for m in shortlist])

        body = [t("models_pick_prompt", lang).format(slot=t(_SLOT_LABEL[slot], lang))]
        rows: list[list[InlineKeyboardButton]] = []
        for idx, m in enumerate(shortlist):
            ctx_len = f"{m['context'] // 1000}k ctx" if m.get("context") else "? ctx"
            body.append(f"• {m['name']} — {ctx_len} — {m['price']}")
            rows.append([InlineKeyboardButton(text=m["name"][:60], callback_data=f"mdl:pick:{idx}")])
        rows.append([InlineKeyboardButton(text=t("btn_custom_slug", lang), callback_data=f"mdl:custom:{slot}")])
        rows.append([InlineKeyboardButton(text=t("btn_reset_slot", lang), callback_data=f"mdl:resetslot:{slot}")])
        await callback.message.answer("\n".join(body), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

    # --- Pick a shortlist model ------------------------------------------
    @router.callback_query(F.data.startswith("mdl:pick:"))
    async def on_pick(callback: CallbackQuery) -> None:
        await callback.answer()
        lang = _lang(callback.message)
        entry = picker.get(callback.message.chat.id)
        if entry is None:
            await callback.message.answer(t("generic_error", lang))
            return
        slot, slugs = entry
        idx = int(callback.data.split(":")[2])
        if idx >= len(slugs):
            return
        slug = slugs[idx]
        await ctx.models.set_user_model(callback.from_user.id, slot, slug)
        await callback.message.answer(t("models_set", lang).format(slug=slug))

    # --- Custom slug (FSM) -----------------------------------------------
    @router.callback_query(F.data.startswith("mdl:custom:"))
    async def on_custom(callback: CallbackQuery, state: FSMContext) -> None:
        await callback.answer()
        slot = callback.data.split(":")[2]
        await state.set_state(ModelStates.awaiting_slug)
        await state.update_data(slot=slot)
        await callback.message.answer(t("models_ask_slug", _lang(callback.message)))

    @router.message(ModelStates.awaiting_slug, private)
    async def on_slug(message: Message, state: FSMContext) -> None:
        lang = _lang(message)
        uid = message.from_user.id
        data = await state.get_data()
        slot = data.get("slot")
        await state.clear()
        slug = (message.text or "").strip()
        if not slot or not slug:
            await message.answer(t("models_invalid", lang))
            return
        key = await ctx.quota.api_key_for(uid)
        if not await ctx.models.slug_exists(slug, key):
            await message.answer(t("models_invalid", lang))
            return
        # Accept a wrong-modality slug but warn (power users may know better).
        await ctx.models.set_user_model(uid, slot, slug)
        ok_modality = await ctx.models.modality_ok(slug, slot, key)
        text = t("models_set", lang).format(slug=slug)
        if not ok_modality:
            text += "\n" + t("models_modality_warn", lang)
        await message.answer(text)

    # --- Resets ----------------------------------------------------------
    @router.callback_query(F.data.startswith("mdl:resetslot:"))
    async def on_reset_slot(callback: CallbackQuery) -> None:
        await callback.answer()
        slot = callback.data.split(":")[2]
        await ctx.models.reset_user_model(callback.from_user.id, slot)
        await callback.message.answer(t("models_reset_done", _lang(callback.message)))

    @router.callback_query(F.data == "mdl:resetall")
    async def on_reset_all(callback: CallbackQuery) -> None:
        await callback.answer()
        await ctx.models.reset_all(callback.from_user.id)
        await callback.message.answer(t("models_reset_all_done", _lang(callback.message)))

    return router

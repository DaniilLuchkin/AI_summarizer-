"""Inline-keyboard callbacks: predefined actions, special generators, custom.

Every callback first clears the spinner and echoes the chosen action, then
dispatches by key: text actions go through the LLM, while presentation / pdf /
image build and send a file (or photo).
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery

from bot.handlers.run import (
    ACTION_CB_PREFIX,
    CustomStates,
    build_actions_keyboard,
    check_llm_limit,
    run_llm,
)
from bot.prompts import (
    CUSTOM_KEY,
    IMAGE_PROMPT_SYSTEM,
    PDF_SYSTEM,
    PRESENTATION_SYSTEM,
    SYSTEM_PROMPTS,
    TEXT_ACTION_KEYS,
    label_key,
)
from bot.runtime import AppContext
from bot.services import pdf_builder, pptx_builder
from bot.texts import resolve_lang, t

logger = logging.getLogger(__name__)

# Telegram caption hard limit.
_CAPTION_LIMIT = 1024


def build_router(ctx: AppContext) -> Router:
    router = Router(name="actions")

    @router.callback_query(F.data.startswith(ACTION_CB_PREFIX))
    async def on_action(callback: CallbackQuery, state: FSMContext) -> None:
        await callback.answer()  # clear Telegram's loading spinner
        key = callback.data[len(ACTION_CB_PREFIX):]
        message = callback.message
        if message is None:
            return

        chat_state = ctx.store.get(message.chat.id)
        lang = chat_state.lang if chat_state else resolve_lang(callback.from_user.language_code)

        if chat_state is None or not chat_state.has_active_batch:
            await message.answer(t("no_active_batch", lang))
            return

        # Echo the chosen action so the chat records what ran.
        await message.answer(t("action_selected", lang).format(label=t(label_key(key), lang)))

        if key == CUSTOM_KEY:
            await state.set_state(CustomStates.waiting_for_instruction)
            await message.answer(t("custom_prompt_ask", lang))
            return

        # Any other action runs immediately: drop a stale custom-prompt state
        # so the next plain message isn't mistaken for context.
        await state.clear()

        document, truncated = ctx.store.assemble_for_llm(chat_state)
        if truncated:
            await message.answer(t("context_truncated", lang))

        user_id = callback.from_user.id

        if key in TEXT_ACTION_KEYS:
            await run_llm(message, ctx, user_id, lang, SYSTEM_PROMPTS[key], document)
        elif key == "presentation":
            await _make_presentation(message, ctx, user_id, lang, document)
        elif key == "pdf":
            await _make_pdf(message, ctx, user_id, lang, document)
        elif key == "image":
            await _make_image(message, ctx, user_id, lang, document)
        else:
            await message.answer(t("generic_error", lang))

    return router


async def _resend_keyboard(message, lang: str) -> None:
    await message.answer(t("followup_hint", lang), reply_markup=build_actions_keyboard(lang))


async def _make_presentation(message, ctx: AppContext, user_id: int, lang: str, document: str):
    if not await check_llm_limit(message, ctx, user_id, lang):
        return
    status = await message.answer(t("building_presentation", lang))
    try:
        raw = await ctx.orclient.chat(
            [
                {"role": "system", "content": PRESENTATION_SYSTEM},
                {"role": "user", "content": document},
            ]
        )
        ctx.limiter.record_llm(user_id)
        # Parsing + rendering are CPU-bound; keep the event loop responsive.
        data = await asyncio.to_thread(pptx_builder.parse_slides, raw)
        pptx_bytes = await asyncio.to_thread(pptx_builder.build_pptx, data)
        await message.answer_document(
            BufferedInputFile(pptx_bytes, filename="presentation.pptx"),
            caption=t("presentation_caption", lang),
        )
    except Exception:  # noqa: BLE001
        logger.exception("Presentation generation failed")
        await message.answer(t("presentation_failed", lang))
    finally:
        await _safe_delete(status)
    await _resend_keyboard(message, lang)


async def _make_pdf(message, ctx: AppContext, user_id: int, lang: str, document: str):
    if not await check_llm_limit(message, ctx, user_id, lang):
        return
    status = await message.answer(t("building_pdf", lang))
    try:
        raw = await ctx.orclient.chat(
            [
                {"role": "system", "content": PDF_SYSTEM},
                {"role": "user", "content": document},
            ]
        )
        ctx.limiter.record_llm(user_id)
        pdf_bytes = await asyncio.to_thread(pdf_builder.build_pdf, raw)
        await message.answer_document(
            BufferedInputFile(pdf_bytes, filename="result.pdf"),
            caption=t("pdf_caption", lang),
        )
    except Exception:  # noqa: BLE001
        logger.exception("PDF generation failed")
        await message.answer(t("pdf_failed", lang))
    finally:
        await _safe_delete(status)
    await _resend_keyboard(message, lang)


async def _make_image(message, ctx: AppContext, user_id: int, lang: str, document: str):
    if not await check_llm_limit(message, ctx, user_id, lang):
        return
    status = await message.answer(t("building_image", lang))
    try:
        prompt = await ctx.orclient.chat(
            [
                {"role": "system", "content": IMAGE_PROMPT_SYSTEM},
                {"role": "user", "content": document},
            ]
        )
        prompt = prompt.strip()
        image_bytes = await ctx.orclient.generate_image(prompt)
        ctx.limiter.record_llm(user_id)
        await message.answer_photo(
            BufferedInputFile(image_bytes, filename="image.jpg"),
            caption=prompt[:_CAPTION_LIMIT],
        )
    except Exception:  # noqa: BLE001
        logger.exception("Image generation failed")
        await message.answer(t("image_failed", lang))
    finally:
        await _safe_delete(status)
    await _resend_keyboard(message, lang)


async def _safe_delete(msg) -> None:
    try:
        await msg.delete()
    except Exception:  # noqa: BLE001
        pass

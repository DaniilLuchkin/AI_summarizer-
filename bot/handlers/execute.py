"""Shared execution: gather optional context and run a staged action / custom.

Used by actions.py (staged predefined actions + custom button) and collect.py
(typed-directly custom prompt). Keeps the "build final instruction, call model,
send result" logic in one place.
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.types import BufferedInputFile, Message

from bot.handlers.run import build_actions_keyboard, check_llm_limit, run_llm
from bot.prompts import (
    CUSTOM_SYSTEM,
    IMAGE_PROMPT_SYSTEM,
    PDF_SYSTEM,
    PRESENTATION_SYSTEM,
    SYSTEM_PROMPTS,
    TEXT_ACTION_KEYS,
)
from bot.runtime import AppContext
from bot.services import context as context_service
from bot.services import media, pdf_builder, pptx_builder
from bot.services.media import FileTooLarge
from bot.texts import t

logger = logging.getLogger(__name__)

MAX_LINKS = 3
_CAPTION_LIMIT = 1024
_PPTX_EXTS = (".pptx", ".potx")


# --- Context gathering ---------------------------------------------------
async def collect_context(
    ctx: AppContext, bot: Bot, message: Message, lang: str
) -> tuple[list[str], bytes | None]:
    """Parse links + an attached file from `message`.

    Returns (text_context_parts, pptx_template_bytes). A .pptx/.potx attachment
    is returned as template bytes (for the Presentation action) rather than
    parsed as text.
    """
    parts: list[str] = []
    template: bytes | None = None
    text = message.text or message.caption or ""

    for url in context_service.extract_urls(text)[:MAX_LINKS]:
        try:
            fetched = await context_service.fetch_link(
                url, ctx.settings.link_fetch_timeout, ctx.settings.context_max_chars
            )
            if fetched:
                parts.append(f"Context from link {url}:\n{fetched}")
                await message.answer(t("context_added_link", lang))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Link fetch failed for %s: %s", url, exc)
            await message.answer(t("context_link_failed", lang).format(url=url, error=exc))

    if message.document:
        name = message.document.file_name or "file"
        lower = name.lower()
        try:
            data = await media.download(bot, message.document.file_id)
            if lower.endswith(_PPTX_EXTS):
                template = data  # used as the presentation base template
                await message.answer(t("context_added_file", lang).format(name=name))
            else:
                parsed = context_service.parse_file(name, data, ctx.settings.context_max_chars)
                if parsed:
                    parts.append(f"Context from file «{name}»:\n{parsed}")
                    await message.answer(t("context_added_file", lang).format(name=name))
        except FileTooLarge:
            await message.answer(t("context_file_failed", lang).format(name=name, error=">20MB"))
        except ValueError:
            await message.answer(t("context_file_failed", lang).format(name=name, error="?"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("File parse failed for %s: %s", name, exc)
            await message.answer(t("context_file_failed", lang).format(name=name, error=exc))

    return parts, template


# --- Content builders ----------------------------------------------------
def _build_action_content(document: str, added_text: str, parts: list[str]) -> str:
    """Predefined action: batch + (optional) user-added instruction/context."""
    blocks = ["=== MESSAGE BATCH ===", document]
    extra = [p for p in [added_text.strip()] if p] + parts
    if extra:
        blocks += ["", "=== ADDITIONAL INSTRUCTION / CONTEXT ===", *extra]
    return "\n".join(blocks)


def _build_custom_content(document: str, instruction: str, parts: list[str]) -> str:
    """Custom prompt: the user's text IS the instruction."""
    blocks = [
        "=== MESSAGE BATCH ===",
        document,
        "",
        "=== USER INSTRUCTION ===",
        instruction.strip() or "(no explicit instruction — act sensibly)",
    ]
    if parts:
        blocks += ["", "=== ADDITIONAL CONTEXT ===", *parts]
    return "\n".join(blocks)


# --- Dispatch ------------------------------------------------------------
async def run_staged(
    ctx: AppContext,
    message: Message,
    bot: Bot,
    lang: str,
    user_id: int,
    action_key: str,
    source_message: Message | None,
) -> None:
    """Run a staged action. `source_message` (if any) supplies optional context."""
    chat_state = ctx.store.get(message.chat.id)
    if chat_state is None or not chat_state.has_active_batch:
        await message.answer(t("no_active_batch", lang))
        return

    document, truncated = ctx.store.assemble_for_llm(chat_state)
    if truncated:
        await message.answer(t("context_truncated", lang))

    added_text = ""
    parts: list[str] = []
    template: bytes | None = None
    if source_message is not None:
        added_text = (source_message.text or source_message.caption or "").strip()
        parts, template = await collect_context(ctx, bot, source_message, lang)

    if action_key == "custom":
        content = _build_custom_content(document, added_text, parts)
        await run_llm(message, ctx, user_id, lang, CUSTOM_SYSTEM, content)
    elif action_key in TEXT_ACTION_KEYS:
        content = _build_action_content(document, added_text, parts)
        await run_llm(message, ctx, user_id, lang, SYSTEM_PROMPTS[action_key], content)
    elif action_key == "presentation":
        content = _build_action_content(document, added_text, parts)
        await _make_presentation(message, ctx, user_id, lang, content, template)
    elif action_key == "pdf":
        content = _build_action_content(document, added_text, parts)
        await _make_pdf(message, ctx, user_id, lang, content)
    elif action_key == "image":
        content = _build_action_content(document, added_text, parts)
        await _make_image(message, ctx, user_id, lang, content)
    else:
        await message.answer(t("generic_error", lang))


async def run_typed_custom(ctx: AppContext, message: Message, bot: Bot, lang: str) -> None:
    """A plain typed text against an active batch == a custom prompt (Change 2)."""
    await run_staged(ctx, message, bot, lang, message.from_user.id, "custom", source_message=message)


# --- Special generators --------------------------------------------------
async def _make_presentation(message, ctx, user_id, lang, content, template):
    if not await check_llm_limit(message, ctx, user_id, lang):
        return
    status = await message.answer(t("building_presentation", lang))
    try:
        raw = await ctx.orclient.chat(
            [{"role": "system", "content": PRESENTATION_SYSTEM}, {"role": "user", "content": content}]
        )
        ctx.limiter.record_llm(user_id)
        data = await asyncio.to_thread(pptx_builder.parse_slides, raw)
        pptx_bytes = await asyncio.to_thread(pptx_builder.build_pptx, data, template)
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


async def _make_pdf(message, ctx, user_id, lang, content):
    if not await check_llm_limit(message, ctx, user_id, lang):
        return
    status = await message.answer(t("building_pdf", lang))
    try:
        raw = await ctx.orclient.chat(
            [{"role": "system", "content": PDF_SYSTEM}, {"role": "user", "content": content}]
        )
        ctx.limiter.record_llm(user_id)
        pdf_bytes = await asyncio.to_thread(pdf_builder.build_pdf, raw)
        await message.answer_document(
            BufferedInputFile(pdf_bytes, filename="result.pdf"), caption=t("pdf_caption", lang)
        )
    except Exception:  # noqa: BLE001
        logger.exception("PDF generation failed")
        await message.answer(t("pdf_failed", lang))
    finally:
        await _safe_delete(status)
    await _resend_keyboard(message, lang)


async def _make_image(message, ctx, user_id, lang, content):
    if not await check_llm_limit(message, ctx, user_id, lang):
        return
    status = await message.answer(t("building_image", lang))
    try:
        prompt = await ctx.orclient.chat(
            [{"role": "system", "content": IMAGE_PROMPT_SYSTEM}, {"role": "user", "content": content}]
        )
        prompt = prompt.strip()
        image_bytes = await ctx.orclient.generate_image(prompt)
        ctx.limiter.record_llm(user_id)
        await message.answer_photo(
            BufferedInputFile(image_bytes, filename="image.jpg"), caption=prompt[:_CAPTION_LIMIT]
        )
    except Exception:  # noqa: BLE001
        logger.exception("Image generation failed")
        await message.answer(t("image_failed", lang))
    finally:
        await _safe_delete(status)
    await _resend_keyboard(message, lang)


async def _resend_keyboard(message, lang: str) -> None:
    await message.answer(t("followup_hint", lang), reply_markup=build_actions_keyboard(lang))


async def _safe_delete(msg) -> None:
    try:
        await msg.delete()
    except Exception:  # noqa: BLE001
        pass

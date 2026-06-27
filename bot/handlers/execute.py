"""Shared execution: gather optional context and run a staged action / custom.

Used by actions.py (staged predefined actions + custom button) and collect.py
(typed-directly custom prompt). Keeps the "build final instruction, call model,
send result" logic in one place.
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.types import (
    BufferedInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from bot.handlers.run import build_actions_keyboard, build_upgrade_keyboard, run_llm
from bot.prompts import (
    CUSTOM_SYSTEM,
    DECK_PLAN_SYSTEM,
    DECK_QA_SYSTEM,
    IMAGE_PROMPT_SYSTEM,
    PDF_SYSTEM,
    SYSTEM_PROMPTS,
    TEXT_ACTION_KEYS,
)
from bot.services import deck_design, deck_qa
from bot.runtime import AppContext
from bot.services import context as context_service
from bot.services import media, pdf_builder, pptx_builder
from bot.services.media import FileTooLarge
from bot.texts import t

logger = logging.getLogger(__name__)

MAX_LINKS = 3
_CAPTION_LIMIT = 1024
_PPTX_EXTS = (".pptx", ".potx")

# Maps a quota reason code to a localized message key.
_LIMIT_TEXT = {
    "llm": "limit_llm",
    "image": "paywall_image",
    "pptx": "paywall_pptx",
    "generic": "paywall_generic",
}


async def _send_paywall(message: Message, reason: str | None, lang: str) -> None:
    """Send a brief limit/paywall message with a one-tap upgrade button."""
    text = t(_LIMIT_TEXT.get(reason or "generic", "paywall_generic"), lang)
    await message.answer(
        f"{text}\n{t('see_plans_hint', lang)}", reply_markup=build_upgrade_keyboard(lang)
    )


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
    preset_instruction: str | None = None,
) -> None:
    """Run a staged action, applying quotas/feature gates and BYO key/model.

    `source_message` supplies optional context; `preset_instruction` is used by
    saved prompts (a fixed custom instruction with no source message).
    """
    chat_state = ctx.store.get(message.chat.id)
    if chat_state is None or not chat_state.has_active_batch:
        await message.answer(t("no_active_batch", lang))
        return

    cap = await ctx.quota.context_cap_for(user_id)
    document, truncated = ctx.store.assemble_for_llm(chat_state, cap)
    if truncated:
        await message.answer(t("context_truncated", lang))

    added_text = ""
    parts: list[str] = []
    template: bytes | None = None
    if preset_instruction is not None:
        added_text = preset_instruction
    elif source_message is not None:
        added_text = (source_message.text or source_message.caption or "").strip()
        parts, template = await collect_context(ctx, bot, source_message, lang)

    # --- Quota / feature gate (the paywall appears at the moment of value) ---
    if action_key == "custom" or action_key in TEXT_ACTION_KEYS or action_key == "pdf":
        ok, reason = await ctx.quota.consume_llm_call(user_id)
    elif action_key == "presentation":
        ok, reason = await ctx.quota.require_pptx(user_id)
    elif action_key == "image":
        ok, reason = await ctx.quota.require_image(user_id)
    else:
        await message.answer(t("generic_error", lang))
        return
    if not ok:
        await _send_paywall(message, reason, lang)
        return

    api_key = await ctx.quota.api_key_for(user_id)
    # Per-task model resolution honours a BYO user's /models overrides.
    model = await ctx.models.resolve(user_id, "text")
    # Pro / BYO users always get the raw markdown answer as result.md too.
    user = await ctx.quota.ensure_user(user_id)
    attach_md = ctx.quota.is_pro(user) or ctx.quota.has_byo(user)

    if action_key == "custom":
        content = _build_custom_content(document, added_text, parts)
        chat_state.last_custom_prompt = added_text.strip() or None
        await run_llm(message, ctx, lang, CUSTOM_SYSTEM, content, model, api_key, attach_md=attach_md)
        if chat_state.last_custom_prompt:
            await _offer_save_prompt(message, lang)
    elif action_key in TEXT_ACTION_KEYS:
        content = _build_action_content(document, added_text, parts)
        await run_llm(
            message, ctx, lang, SYSTEM_PROMPTS[action_key], content, model, api_key,
            attach_md=attach_md,
        )
    elif action_key == "presentation":
        content = _build_action_content(document, added_text, parts)
        photos = {p["id"]: p["bytes"] for p in chat_state.photos}
        if photos:
            content += "\n\n=== AVAILABLE PHOTOS ===\n" + "\n".join(
                f"#{p['id']}: {_first_line(p['desc'])}" for p in chat_state.photos
            )
        want_gallery = bool(photos) and _wants_images(added_text)
        await _make_presentation(
            message, ctx, lang, content, template, api_key, user_id,
            photos, want_gallery, t("slides_gallery_title", lang),
        )
    elif action_key == "pdf":
        content = _build_action_content(document, added_text, parts)
        await _make_pdf(message, ctx, lang, content, model, api_key)
    elif action_key == "image":
        content = _build_action_content(document, added_text, parts)
        image_model = await ctx.models.resolve(user_id, "image")
        await _make_image(message, ctx, lang, content, model, api_key, image_model)


async def run_typed_custom(ctx: AppContext, message: Message, bot: Bot, lang: str) -> None:
    """A plain typed text against an active batch == a custom prompt (Change 2)."""
    await run_staged(ctx, message, bot, lang, message.from_user.id, "custom", source_message=message)


async def _offer_save_prompt(message: Message, lang: str) -> None:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t("btn_save_prompt", lang), callback_data="save_prompt")]]
    )
    await message.answer(t("save_prompt_offer", lang), reply_markup=keyboard)


# Keywords (en/ru/uk) that signal the user wants the photos in the deck.
_IMAGE_WORDS = (
    "photo", "image", "picture", "pic", "foto",
    "фото", "изображ", "картинк", "снимк", "зображ", "світлин",
)


def _wants_images(instruction: str) -> bool:
    low = (instruction or "").lower()
    return any(w in low for w in _IMAGE_WORDS)


def _first_line(text: str) -> str:
    line = (text or "").strip().splitlines()[0] if (text or "").strip() else ""
    return line[:120]


# --- Special generators --------------------------------------------------
async def _make_presentation(
    message, ctx, lang, content, template, api_key, user_id,
    photos=None, want_gallery=False, gallery_title="Images",
):
    photos = photos or {}
    s = ctx.settings
    status = await message.answer(t("building_presentation", lang))
    try:
        # 1) Plan the deck with the strong planning model (BYO key if set).
        raw = await ctx.orclient.chat(
            [{"role": "system", "content": DECK_PLAN_SYSTEM}, {"role": "user", "content": content}],
            model=s.deck_model, api_key=api_key,
        )
        plan = await asyncio.to_thread(pptx_builder.parse_slides, raw)
        plan = deck_design.normalize_plan(plan)
        _append_photo_gallery(plan, photos, want_gallery, gallery_title)

        if template:
            # Template mode: keep the company theme/layouts; column logic keeps
            # text and images apart, so we skip the render-based QA loop.
            pptx_bytes = await asyncio.to_thread(
                pptx_builder.build_pptx,
                pptx_builder.flatten_for_template(plan), template, photos, False, gallery_title,
            )
        else:
            pptx_bytes = await asyncio.to_thread(pptx_builder.build_design, plan, photos, {})
            if s.deck_qa_enabled:
                try:
                    await status.edit_text(t("deck_polishing", lang))
                except Exception:  # noqa: BLE001 - status edit is cosmetic
                    pass
                pptx_bytes = await _polish_deck(ctx, plan, photos, api_key, user_id, pptx_bytes)

        await message.answer_document(
            BufferedInputFile(pptx_bytes, filename="presentation.pptx"),
            caption=t("presentation_caption", lang),
        )
    except Exception:  # noqa: BLE001
        logger.exception("Presentation generation failed")
        await message.answer(t("presentation_failed", lang))
    finally:
        await _safe_delete(status)


def _append_photo_gallery(plan: dict, photos: dict, want_gallery: bool, title: str) -> None:
    """When the user asked for the photos, ensure every unreferenced one appears."""
    if not (want_gallery and photos):
        return
    referenced = {s.get("image_ref") for s in plan["slides"] if isinstance(s.get("image_ref"), int)}
    for pid in sorted(photos):
        if pid not in referenced:
            plan["slides"].append({"layout": "image_feature", "title": title, "image_ref": pid})


async def _polish_deck(ctx, plan, photos, api_key, user_id, deck_bytes):
    """Run the bounded visual-QA loop; on any failure ship the input deck."""
    s = ctx.settings

    async def detect_slide(slide_no: int, jpg: bytes) -> str:
        # QA vision calls count toward usage like other calls (best-effort).
        try:
            await ctx.quota.consume_llm_call(user_id)
        except Exception:  # noqa: BLE001
            pass
        prompt = f"{DECK_QA_SYSTEM}\nThis is slide {slide_no} of the deck."
        return await ctx.orclient.vision(jpg, prompt, "image/jpeg", api_key=api_key, model=s.qa_vision_model)

    def rebuild(overrides: dict) -> bytes:
        return pptx_builder.build_design(plan, photos, overrides)

    return await deck_qa.polish(
        deck_bytes=deck_bytes, rebuild=rebuild, detect_slide=detect_slide,
        max_passes=s.deck_qa_max_passes, max_slides=s.deck_qa_max_slides,
    )
    await _resend_keyboard(message, lang)


async def _make_pdf(message, ctx, lang, content, model, api_key):
    status = await message.answer(t("building_pdf", lang))
    try:
        raw = await ctx.orclient.chat(
            [{"role": "system", "content": PDF_SYSTEM}, {"role": "user", "content": content}],
            model=model, api_key=api_key,
        )
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


async def _make_image(message, ctx, lang, content, model, api_key, image_model=None):
    status = await message.answer(t("building_image", lang))
    try:
        # `model` writes the image prompt (text slot); `image_model` renders it.
        prompt = await ctx.orclient.chat(
            [{"role": "system", "content": IMAGE_PROMPT_SYSTEM}, {"role": "user", "content": content}],
            model=model, api_key=api_key,
        )
        prompt = prompt.strip()
        image_bytes = await ctx.orclient.generate_image(prompt, api_key=api_key, model=image_model)
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

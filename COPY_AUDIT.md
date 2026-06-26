# Forwardly AI — communication audit

A copy/UX pass over every user-facing string in all three languages (en/ru/uk).
**No behavior, logic, pricing, or limit changes** — only wording, structure, and
discoverability. All user-facing text lives in `bot/texts.py`.

Method: read the actual handlers/services first (collect, actions, execute,
commands, billing, account, group, models, quota/openrouter), then reconciled the
copy against real behavior.

---

## 1. Accuracy fixes (copy diverged from behavior)

- **Welcome was outdated.** It told users to "tap ✍️ Custom prompt" and implied
  context could only be attached to a *custom* prompt. Reality (since the
  editable-actions change): you can **just type a prompt** with no tap, and you
  can add context (text/file/link) to **any** action. Rewrote the welcome to
  match, and added the facts that the **answer comes back in the source-message
  language** and that it points to `/help` and `/plans`.
- **Presentation template was invisible.** The Presentation action accepts a
  `.pptx/.potx` company template, but no copy said so. Added a tailored
  `presentation_context_hint` shown only when the Presentation action is staged.
- **`/help` was a flat dump** and omitted the file-size cap, long-audio splitting,
  and "answers can arrive as a file." Rewrote it grouped (Everyday / Plan & limits
  / Your key & models / Prompts / Friends & data / In groups) with those facts.

## 2. Dead-ends removed

- **`/forgetme` cancel** replied with a bare "❌" (no words). Now a localized
  `forgetme_cancelled` ("Cancelled — your data is untouched.").
- **Save-prompt offer** posted a bare "💾" with a button. Now a localized
  `save_prompt_offer` ("Save this prompt to run it again later?").
- **Forget confirm buttons** were ambiguous "✅ / ❌". Now localized
  `btn_confirm_delete` / `btn_cancel` ("Yes, delete" / "Cancel").

## 3. Strings moved out of handlers into `texts.py`

Previously hardcoded (English-only) and now localized keys:

- `invoice_title`, `invoice_description` — the Telegram Stars invoice (`billing.py`).
- `save_prompt_offer` (`execute.py`).
- `forgetme_cancelled`, `btn_confirm_delete`, `btn_cancel` (`account.py`).
- `models_default` — the "default:" prefix in the `/models` overview (`models.py`).

After this pass, a grep for user-facing literals in handlers is clean (only
callback-data, file names, and language self-names remain hardcoded, which is
correct).

## 4. Button truncation (Telegram clips long inline labels on phones)

Shortened the predefined-action labels that truncated (e.g. "📝 Краткое
содержание" → "📝 Кратко"). Kept terminology consistent with the rest of the copy.

| key | before (ru) | after (ru) | en | uk |
|---|---|---|---|---|
| summary | Краткое содержание | Кратко | Summary | Стисло |
| structure | Структурировать | Структура | Structure | Структура |
| reply | Черновик ответа | Ответ | Reply | Відповідь |
| email | Follow-up письмо | Письмо | Follow-up | Лист |
| items | Задачи и решения | Задачи | Action items | Завдання |
| translate | Перевести (EN) | Перевод EN | Translate EN | Переклад EN |

`presentation` / `pdf` / `image` were already short enough and kept (terminology
parity with `/plans` and the paywalls).

## 5. Surfaced previously-hidden capabilities

- **"Just type a prompt"** — added to the welcome and to `batch_ready` ("Pick an
  action — or just type your prompt"); the full-width custom button already says
  this and its ⬇️ points at the input box.
- **Add context to any action / Run without it** — stated in welcome + help.
- **`.pptx/.potx` template** — `presentation_context_hint`.
- **Answer follows the source language** — welcome + help.
- **20 MB cap, auto-split long audio, long answers as a file** — help.
- **Pro renewal/cancel** — `stars_renew_note` appended to the purchase screen
  ("Stars auto-renews, cancel in Telegram; crypto is a one-off for 30 days").

## 6. Consistency

- One term per concept kept across features and languages: batch = "пачка",
  prompt = "запрос/запит", Pro, context. Button labels reuse the same words as
  `/plans` and the paywalls.
- "Photos" in limits already read as **photo analyses** (OCR/vision input), not
  generated images, in `usage_report` — left as is (accurate).

## 7. Parity & placeholders (verified)

- All **128 keys** exist in en/ru/uk (no English leaking to ru/uk via the `t()`
  fallback).
- Every `{placeholder}` set is identical across the three languages for each key
  (checked programmatically) and is filled at its call site.

---

## Files touched

`bot/texts.py` (the bulk), `bot/handlers/billing.py`, `bot/handlers/account.py`,
`bot/handlers/execute.py`, `bot/handlers/actions.py`, `bot/handlers/models.py`.
No service/logic files changed. The command menus (`commands_menu.py`) already
matched the implemented commands and were left unchanged.

## Not changed (deliberately)

- Pricing, limits, models, flow, routing — out of scope.
- The internal `[i] Name (kind): body` item labels (`KIND_*`) stay English: they
  are technical scaffolding fed to the model, not UI chrome.

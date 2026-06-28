# Forwardly AI — code & function audit

Functional/structural counterpart to `COPY_AUDIT.md`. Scope: behavior and UX
structure (not wording). Flows were traced end‑to‑end through the handlers and
services (collect, actions, execute, commands, billing, account, models, group,
quota, openrouter, render/delivery, db, pptx/deck).

**Phasing:** §1 lists what was found. §2 are the clearly‑safe fixes **already
applied in this pass**. §3 is **proposals that need your approval** (feature
add/remove/merge, action‑grid restructuring) — none of those are applied.

Verified after the §2 fixes: `py_compile` clean, all `bot.*` modules import,
routers build, en/ru/uk text parity holds (125 keys each), render/delivery unit
checks still pass.

---

## 1. Findings

### A. Correctness & resilience

| # | Sev | Area | Finding | Disposition |
|---|-----|------|---------|-------------|
| A1 | Med | execute.py | **Action keyboard lost after a presentation.** `_make_presentation` never re‑showed the “run another action” grid (PDF and Image both do). The intended call was sitting as **unreachable dead code after a `return`** inside `_polish_deck`, where it also referenced undefined `message`/`lang` (would `NameError` if it were ever reached). | **Fixed (§2.1)** |
| A2 | Low | collect.py | **Finalize race.** A message arriving while `_finalize` is mid‑`await` seeds a fresh `pending` batch (since `has_active_batch` only flips at the end), which can finalize into a second batch. No crash, no double‑charge; cosmetically you can get two “batch ready” prompts. | Documented; not fixed (harmless) |
| A3 | Low | delivery.py | **Streaming draft is best‑effort.** `sendMessageDraft` is attempted first; if Telegram doesn’t honor it for this bot it falls back to a placeholder + throttled `editMessageText`. Fallback verified; capability is probed once and cached per process. Final answer is persisted exactly once (HTML, or `result.md` when long). | OK by design |
| A4 | — | deck_qa / execute / billing / context | **Fallback chains verified.** QA render/detect/rebuild each wrapped → ships the un‑QA’d deck on any failure (`polish` never raises). `_make_pdf/_make_image/_make_presentation` wrapped → friendly message. Streaming→edit and HTML→plain both fall back. Link fetch / file parse / ffmpeg / OpenRouter / crypto all wrapped. | OK |
| A5 | — | collect.py | **Edge cases handled:** empty batch → `empty_batch`; >20 MB → `FileTooLarge` → `skipped_too_large`; video w/o audio track → `skipped_no_audio` (keeps caption if any); audio >55s → segmented & stitched; quota exhausted mid‑batch → per‑item skip note + one `upgrade_hint`. | OK |
| A6 | — | follow‑ups | **No re‑transcription / no double charge on follow‑ups.** Follow‑up actions reuse `chat_state.item_texts`; media is transcribed/OCR’d once at finalize and additionally cached in `media_cache` by `file_unique_id`. | OK |

### B. Quick‑action buttons / keyboards

Full inventory in the **button table** below. Headline: **every callback has a
live handler and is reachable; no orphan buttons; no truncation risk.** The one
structural concern is the **size of the main action grid (10 actions)** — see
§3.1 (needs approval).

### C. Gaps & orphans
- **C1 — `PRESENTATION_SYSTEM` (prompts.py):** orphaned; the deck path uses
  `DECK_PLAN_SYSTEM`. **Removed (§2.4).**
- **C2 — In‑memory LLM/day rate limiter (ratelimit.py):** `check_llm`/`record_llm`
  + the `MAX_LLM_CALLS_PER_DAY` config were never called — the real per‑day LLM
  cap is the DB‑backed `free/pro_daily_llm_calls` in `quota.py`. **Removed (§2.3).**
- **C3 — `limit_audio` / `limit_photo` text keys:** defined but never shown. When
  an audio/photo item is quota‑blocked, `collect.py` shows the per‑item
  `item_not_transcribed` / `item_not_ocr` and discards the reason code. Harmless
  redundancy. **Kept** (semantically reasonable) — flagged for your call.
- **C4 — Saved prompts vs. active batch:** `/prompts → run` requires an active
  batch, otherwise it replies `no_active_batch`. Correct, but mildly confusing if
  a user opens `/prompts` with nothing staged. See §3.3.

### D. Dead / duplicate code
- **D1 — `output.send_result`:** dead since PR #14 routed all text answers through
  `services/delivery.py`. Removed the function + the now‑unused `FILE_THRESHOLD_CHARS`
  / `MAX_MESSAGE_CHUNKS` constants; kept `_split_text` + `TELEGRAM_MESSAGE_LIMIT`
  (used by render/delivery). **Fixed (§2.2).**
- **D2 — 8 orphan text keys** (provably unreferenced, incl. dynamic builders):
  `btn_attach`, `btn_send`, `context_none_found`, `custom_add_context_q`,
  `custom_prompt_empty`, `custom_send_context`, `group_media_skipped`,
  `rate_limit_llm` — leftovers from earlier iterations. **Removed across
  en/ru/uk (§2.6).**
- **D3 — Hardcoded non‑English string** in `context.py` (`"…(контекст обрезан)"`)
  appended to truncated link/file context fed to the model. Model‑facing, not UI,
  but shouldn’t be a hardcoded Russian literal. **Neutralized to English (§2.7).**
- **D4 — USDT formatting drift:** `billing.buy_crypto` showed the raw float
  (`4.0 USDT`) while everywhere else uses `fmt_usdt` (`4 USDT`). **Fixed (§2.5).**
- **No payment/render duplication:** the Stars + crypto rails share `grant_pro`,
  and `/pro` + the upgrade button share `show_purchase_options` — they have **not**
  drifted into copies. Output/render is single‑sourced in `delivery.py`.

### E. Simplicity of the experience
- **E1 — Action grid breadth (10 actions).** Highest‑leverage simplification; see
  §3.1.
- **E2 — Pro‑only actions are unmarked in the grid.** Free users see 📊 Presentation
  and 🎨 Image with no lock hint; the paywall appears only after they tap **Run**.
  Intentional (“paywall at the moment of value”) but can surprise. See §3.2.
- **E3 — Two‑tap predefined actions.** Tapping an action stages it and asks for
  optional context (then **Run**). Good for power users; one extra tap for the
  common “just do it” case. See §3.4.

### F. Security & cost
- **F1 — BYO keys:** deleted from chat on `/setkey`, validated, **encrypted at rest**
  (Fernet), decrypted only in memory, **never logged**. ✓
- **F2 — Payments:** `charge_id` recorded in `payments`; per‑day velocity guard;
  admin notification wrapped so it can’t break a flow. ✓
- **F3 — Cost controls:** `media_cache` avoids re‑billing transcription/vision;
  OpenRouter catalog cached ~1h; QA loop bounded (≤2 passes, slide cap). ✓
- **F4 — Cost note (by design):** each QA vision pass consumes one LLM quota unit
  from the user (best‑effort) even though it’s an internal call. Intentional, but
  worth knowing it draws down the daily LLM allowance.

---

## Button audit table

Keyboards: main action grid (`run.py`), run/context (`run.py`), upgrade
(`run.py`), purchase (`billing.py`), `/plans`, `/models` (`models.py`), saved
prompts (`account.py`), forget‑me (`account.py`), language (`commands.py`).

| Button (callback) | Handler | Gating | Verdict | Rationale |
|---|---|---|---|---|
| Summary `act:summary` | actions.on_action | free | **keep** | Core, most‑used. |
| Structure `act:structure` | actions.on_action | free | **review/merge** | Overlaps Summary (both reshape text). Candidate to move under “More…”. §3.1 |
| Reply `act:reply` | actions.on_action | free | **keep** | Distinct intent. |
| Email `act:email` | actions.on_action | free | **review** | Niche variant of Reply; candidate for “More…”. §3.1 |
| Action items `act:items` | actions.on_action | free | **keep** | Distinct, high value. |
| Translate `act:translate` | actions.on_action | free | **keep** | Distinct, high value. |
| Presentation `act:presentation` | actions.on_action → require_pptx | **Pro** | **keep + regate hint** | Heavy export; mark Pro in‑grid. §3.2 |
| PDF `act:pdf` | actions.on_action → consume_llm | free | **review** | Lowest‑signal export; consider “More…” or removal. §3.1 |
| Image `act:image` | actions.on_action → require_image | **Pro** | **keep + regate hint** | Mark Pro in‑grid. §3.2 |
| Custom `act:custom` | actions.on_action | free | **keep** | The “anything else” escape hatch. |
| ▶️ Run `run:now` | actions.on_run | — | **keep** | Runs staged action with no context. |
| ⭐ Upgrade `upgrade` | billing.on_upgrade | — | **keep** | Single upgrade entry point. |
| Pay Stars `buy:stars` | billing.buy_stars | — | **keep** | — |
| Pay Crypto `buy:crypto` | billing.buy_crypto | shown only if token set | **keep** | Correctly conditional. |
| Paid – check `cpay:<id>` | billing.crypto_check | — | **keep** | — |
| Language `lang:<code>` | commands.set_lang_cb | — | **keep** | — |
| Save prompt `save_prompt` | account.save_prompt | free cap | **keep** | — |
| Prompt run/del `prompt:run/del:<id>` | account.prompt_run/delete | — | **keep** | — |
| Forget yes/no `forget:*` | account.forget_cb | — | **keep** | — |
| /models change/pick/custom/reset `mdl:*` | models.* | **BYO only** | **keep** | Correctly gated. |

No button is unreachable, mislabeled into truncation, or missing a handler.

---

## 2. Clearly‑safe fixes APPLIED in this pass

1. **A1 — Restore the action grid after a presentation** and delete the
   unreachable post‑`return` line in `_polish_deck` (`execute.py`).
2. **D1 — Remove dead `output.send_result`** + unused size constants; keep the
   splitter (`output.py`).
3. **C2 — Remove the unused in‑memory LLM/day limiter** (`ratelimit.py`) and its
   orphan config `MAX_LLM_CALLS_PER_DAY` (`config.py`, `.env.example`, `main.py`).
4. **C1 — Remove orphan `PRESENTATION_SYSTEM`** (`prompts.py`; updated the
   `pptx_builder.py` docstring reference).
5. **D4 — Consistent USDT formatting** in the crypto purchase screen (`billing.py`).
6. **D2 — Remove 8 dead text keys** across en/ru/uk (`texts.py`).
7. **D3 — Neutralize the hardcoded Russian truncation marker** to English
   (`context.py`).

No behavior, pricing, or limit changes beyond these defect fixes.

---

## 3. Proposed changes — RESOLVED with your decisions

### 3.1 Tighten the main action grid → **APPROVED & APPLIED**
New layout (the gating/routing in `execute.py` is unchanged):

> Primary: **📝 Summary · 💬 Reply · ✅ Action items · 🌐 Translate · ✍️ Custom · ✨ More…**
> More…: **📋 Structure · ✉️ Follow‑up · 📊 Presentation · 📄 PDF · 🎨 Image · ⬅️ Back**

“More…” swaps the keyboard in place (`more:open` / `more:back` callbacks in
`actions.py`; `PRIMARY_ACTION_KEYS` / `MORE_ACTION_KEYS` in `prompts.py`).

### 3.2 Mark Pro‑only actions → **APPROVED & APPLIED**
Presentation and Image show a **🔒** in the More… submenu **only for non‑Pro /
non‑BYO users** (the submenu is built on a callback, so entitlement is known
without extra plumbing). Pro/BYO users see no lock. The paywall‑on‑Run is
unchanged.

### 3.3 PDF → **move to “More…”, keep** (per your decision) — APPLIED
PDF lives in the More… submenu (free, ungated). Not removed.

### 3.4 One‑tap “run now” default → **keep current staged flow** (per your
decision) — no change.

### 3.5 `limit_audio` / `limit_photo` → **keep limits, mark on exhaustion** (per
your decision). Already satisfied: audio/photo limits are enforced in `quota.py`,
each blocked item is marked (`item_not_transcribed` / `item_not_ocr`), and the
batch shows an upgrade nudge. No change needed; the two extra keys remain
available for future use.

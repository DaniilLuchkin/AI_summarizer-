# Code review — Forwardly AI

Three-pass review (security, correctness, cleanliness) of the bot codebase
(Python 3.12, aiogram 3.x, asyncpg, httpx, OpenRouter, Telegram Stars, Railway).
Findings are grouped by pass with severity + `file:line` + fix. Unambiguous
fixes were applied in this pass (§ "Applied fixes"); behavioural/judgment items
are in § "Needs decision" and were **not** changed. The bot builds and runs
after the changes (compile, imports, dispatcher, parity, and targeted unit tests
all pass).

---

## Pass 1 — Security

| # | Sev | Where | Finding | Status |
|---|-----|-------|---------|--------|
| S1 | **High** | `services/context.py` `fetch_link` | **SSRF.** User-supplied links (custom-prompt context) were fetched with `follow_redirects=True`, no host validation, and no size cap — a link resolving to `localhost`, RFC-1918, link-local (`169.254.169.254` cloud metadata), or reserved space would be fetched, and a public URL could redirect there. | **Fixed** |
| S2 | **High** | `handlers/billing.py` `on_successful_payment` | **Non-idempotent payments.** Telegram may redeliver `successful_payment`; each delivery granted credits / Pro again (the Pro velocity guard only capped it at 3/day, packs had no guard at all). | **Fixed** |
| S3 | **Medium** | `handlers/billing.py` `pre_checkout` | `pre_checkout_query` answered `ok=True` unconditionally instead of validating the payload. | **Fixed** |
| S4 | **Low** | `handlers/billing.py` `buy_pack` | Invoiced whatever pack size arrived in `callback_data` (`pack:<n>`) rather than a configured size. Not directly exploitable (the user pays the matching Stars amount), but the amount/credits should come only from server config. | **Fixed** |

**Verified clean:**
- **SQL** — every query uses `$1` placeholders. The only dynamic SQL (`db.set_user_model`) interpolates a column name from a hard-coded whitelist (`_MODEL_COLUMNS`), never user data. No f-string/`%` SQL with user input.
- **BYO keys** — Fernet-encrypted at rest, decrypted only at call time; `/setkey` deletes the submitting message; the key is never logged (OpenRouter error logs show the response body, not the `Authorization` header). There is no command that echoes the key.
- **Subprocess** — ffmpeg/ffprobe run via `create_subprocess_exec` with argument lists (no `shell=True`); temp files use `tempfile`/`TemporaryDirectory` and are cleaned up.
- **Authorization** — `AccessMiddleware` is an **outer** middleware on `event_from_user`, so `ALLOWED_USER_IDS` gates messages, callbacks, and payments alike. Group `/clear` checks `get_chat_member` status server-side; admin notifications gated by `ADMIN_USER_ID`. Charge/grant always use `message.from_user.id` / `callback.from_user.id`, never an id from `callback_data`.
- **DoS/cost** — caps on file size (20 MB), batch size, context chars, link fetch (now size + time + redirect-bounded). The 0-balance soft-check plus atomic `charge_credits` (row lock, refuses to go negative) means a race can at worst give one tiny free answer, never unbounded global-key spend (see N1).

## Pass 2 — Correctness & bugs

| # | Sev | Where | Finding | Status |
|---|-----|-------|---------|--------|
| C1 | Low | `services/deck_qa.py:45,53` | Blocking `subprocess.run` (sync) in an otherwise-async module. Only reachable via presentations, which are feature-flagged **off** and unwired, so it never runs in a handler today. | Noted (N4) |

**Verified clean:**
- **Money/credits** — amounts are integer tenths end-to-end (`credits.py`, `db.py`); daily bucket spent first; `refresh_daily` is set-not-add and yields floor 0 for Pro; text charged **after** the response by `input+output` tokens with a 0.1-credit minimum; audio charged by real ffprobe seconds; follow-ups reuse the assembled `item_texts` (no re-transcription / re-charge); one ledger row per bucket per grant/charge. All time uses UTC consistently.
- **State/lifecycle** — batch replacement clears context, retained photos, `last_custom_prompt`, and cancels the debounce timer; `/reset` and replacement both cancel timers; the `replaced_previous` notice fires exactly once. FSM `awaiting_input` exits via message/Run/any command (`/reset`).
- **Async hygiene** — no blocking IO in the live handler paths; the shared `httpx.AsyncClient`, the asyncpg pool, and the bot session are all closed in `main._run`'s `finally`; per-call link clients use `async with`. The DNS lookup in the new SSRF guard uses async `loop.getaddrinfo` (non-blocking).
- **Telegram specifics** — `callback.answer()` on every callback; streaming draft → placeholder-edit → plain and HTML → plain fallbacks both fall through on `TelegramBadRequest`; the ephemeral draft is always finalized into a real message; message splitting renders each source chunk independently so a split never lands inside an HTML tag.
- **Error handling** — external calls are wrapped; the debounce/finalize background task swallows nothing silently (it logs and posts a localized `generic_error`); no bare `except:`.

## Pass 3 — Dead & messy code

| # | Sev | Where | Finding | Status |
|---|-----|-------|---------|--------|
| D1 | Low | `texts.py` | Dead text key `presentation_context_hint` (×3) — orphaned when the action grid went text-only. | **Fixed (removed)** |

**Verified clean:** en/ru/uk parity holds (125 keys each) with no missing referenced keys; no hardcoded user-facing strings outside `texts.py` (the only inline markup is `<b>{label}</b>` with a localized label); `requirements.txt` deps are all used — `python-pptx`/`fpdf2` are intentionally retained for the flag-off PDF/PPTX builders (kept but unwired, per design). No commented-out blocks or stale TODOs.

---

## Applied fixes (this pass)

1. **S1 SSRF** — `fetch_link` now validates every URL (and every redirect hop) via `_guard_url`: rejects non-http(s) and any host resolving to a private/loopback/link-local/reserved/multicast address, follows redirects manually (max 4, each revalidated), and caps the download at 5 MB.
2. **S2 idempotency** — `db.payment_exists(charge_id)`; `on_successful_payment` returns early if the charge id was already recorded, so a redelivery never double-grants.
3. **S3 pre_checkout** — approves only `pro_sub` or a `pack:<n>` whose `n` is a configured pack size; otherwise answers `ok=False`.
4. **S4 pack validation** — `buy_pack` (and `on_successful_payment`) ignore any pack size not in `CREDIT_PACKS`.
5. **D1** — removed the dead `presentation_context_hint` key from all three languages.

No pricing, limits, or user-facing behaviour changed beyond these defect fixes.

## Needs decision (unchanged)

- **N1 — Charge/grant concurrency.** `charge_credits` is atomic (row lock, never goes negative), so simultaneous actions can't double-spend or overdraw. The only residual is that two near-simultaneous text actions could both pass the pre-call `balance > 0` soft-check and both be delivered while only one post-charge succeeds — i.e. at most one tiny free answer. This matches the "generous by design" intent; a strict fix (reserve-then-settle before generating) would change behaviour and add latency. Recommend leaving as-is.
- **N2 — Hard payment idempotency.** The app-level `payment_exists` check covers Telegram's sequential redelivery. A `UNIQUE` index on `payments.charge_id` would also cover concurrent redelivery, but `CREATE UNIQUE INDEX` fails at startup if any duplicate charge ids already exist. Recommend: dedupe existing rows, then add the partial unique index in a maintenance migration.
- **N3 — Test pricing.** `PRO_PRICE_STARS=1` and the `1`-credit pack are intentional test values (marked TEST in `config.py`/`.env.example`); revert (250 ⭐, `100,500,1000`) before a real launch.
- **N4 — `deck_qa` blocking subprocess (C1).** Only matters if presentations are re-enabled; convert those `subprocess.run` calls to `asyncio.create_subprocess_exec` at that time.

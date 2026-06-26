# Telegram LLM message-processing bot

A Telegram bot that turns a **batch of mixed messages** — text, voice,
video notes ("кружочки"), videos, audio, documents and photos — into one
combined text document, then runs LLM **actions** on it (summary, structure,
draft reply, follow-up email, action items, translate, **presentation**,
**PDF**, **image**) or a free-text **custom prompt** with optional file/link
context.

Everything (chat, vision/OCR, transcription, image generation) goes through a
**single OpenRouter API key**. The UI is **multilingual (ru / en / uk)**, chosen
from each user's Telegram `language_code`. State is **in-memory only** — no
database.

---

## How it works

1. You forward or send several messages in a row.
2. After ~2.5s of silence (debounce) the bot finalizes the batch:
   - text/captions are kept as-is,
   - voice / video note / video / audio → transcribed (auto-segmented if > ~60s),
   - photos → vision model extracts text (OCR) + a one-line description,
   - documents (`.pdf/.docx/.txt/.md`) → parsed to text.
   Each item is labeled with the **sender's name**, e.g.
   `[1] Иван Петров (voice → transcript): …`, `[3] Ты (photo → ocr): …`.
3. The bot shows an inline keyboard of actions.
4. Tap a predefined action, or **✍️ Custom prompt** to type your own
   instruction. The bot then asks whether to **attach context** (a file or a
   link), which is parsed and appended before the LLM call.
5. The batch stays active — run as many actions/custom prompts as you like.
   Send new messages (or `/reset`) to start a fresh batch.

### Actions
Text actions (📝 Summary, 📋 Structure, 💬 Draft reply, ✉️ Follow-up email,
✅ Action items, 🌐 Translate) reply in chat. Long answers split into multiple
messages; very long ones arrive as `result.md`. Generators produce files/photos:
- **📊 Presentation** → `.pptx` (python-pptx) built from a JSON slide spec.
- **📄 PDF** → `.pdf` (fpdf2 + DejaVu font, full Cyrillic) from structured text.
- **🎨 Image** → a generated image (OpenRouter image model) with its prompt as caption.

### Commands
- `/start` — usage help (localized)
- `/reset` — clear the current batch

---

## Project layout

```
bot/
  main.py              # bootstrap: settings, dispatcher, routers, polling
  config.py            # env settings (pydantic-settings)
  texts.py             # UI strings in ru/en/uk + t() / resolve_lang() helpers
  prompts.py           # system prompts for actions + generators + vision/custom
  middleware.py        # ALLOWED_USER_IDS access control (localized)
  output.py            # send result as message(s) or .md file
  runtime.py           # shared service container (AppContext)
  handlers/
    commands.py        # /start, /reset
    collect.py         # batch collection + debounce + finalize + sender names
    actions.py         # keyboard callbacks: text actions + pptx/pdf/image + echo
    custom.py          # custom-prompt FSM + "add context?" step
    run.py             # actions keyboard + rate-limited LLM call (shared)
  services/
    openrouter.py      # async chat / vision / transcription / image client
    media.py           # download + ffmpeg/ffprobe helpers
    transcribe.py      # audio bytes -> text (with segmentation)
    vision.py          # photo -> text
    context.py         # files (pdf/docx/txt/md) + links -> text
    batch.py           # in-memory batch store + assembly (+ per-chat lang)
    ratelimit.py       # in-memory per-user limiter
    pptx_builder.py    # JSON slide spec -> python-pptx file
    pdf_builder.py     # structured text -> fpdf2 PDF (DejaVu/Cyrillic)
requirements.txt
Dockerfile             # python:3.12-slim + ffmpeg + fonts-dejavu-core
.env.example
```

---

## Run locally

Requirements: **Python 3.12** and **ffmpeg/ffprobe** on your `PATH`.

```bash
# 1. Install ffmpeg + DejaVu fonts (Debian/Ubuntu)
sudo apt-get install -y ffmpeg fonts-dejavu-core
#    macOS: brew install ffmpeg   (DejaVu ships with most macOS setups;
#    if PDF generation can't find it, install a DejaVuSans.ttf system-wide)

# 2. Create a virtualenv and install deps
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Postgres (required) — e.g. via Docker
docker run -d --name forwardly-pg -e POSTGRES_PASSWORD=pg -p 5432:5432 postgres:16
#    then set DATABASE_URL=postgresql://postgres:pg@localhost:5432/postgres

# 4. Configure
cp .env.example .env
#    edit .env: set TELEGRAM_BOT_TOKEN, OPENROUTER_API_KEY, DATABASE_URL, APP_SECRET
#    (APP_SECRET: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
#    and CONFIRM the MODEL_* slugs at https://openrouter.ai/models

# 5. Run
python -m bot.main
```

The bot uses **long polling**, so no public URL/port is needed.

> Tip: lock the bot to yourself while testing by setting
> `ALLOWED_USER_IDS=<your-telegram-id>` in `.env`. Leave it empty for public.

---

## Deploy on Railway (Dockerfile)

This bot runs as a **worker** (outbound only, no HTTP port).

1. Push this repo to GitHub.
2. In Railway: **New Project → Deploy from GitHub repo**, pick this repo.
   Railway auto-detects the `Dockerfile` (which installs `ffmpeg`).
3. **Add the Postgres plugin** (New → Database → PostgreSQL). Railway injects
   `DATABASE_URL` automatically — the bot **requires** it and won't start without it.
4. Open the service → **Variables** and add the values from `.env.example`:
   - `TELEGRAM_BOT_TOKEN`
   - `OPENROUTER_API_KEY`
   - `MODEL_TEXT`, `MODEL_VISION`, `MODEL_TRANSCRIBE`, `MODEL_IMAGE` *(confirm slugs first)*
   - `APP_SECRET` *(Fernet key — see `.env.example`; needed for bring-your-own-key)*
   - billing/quota vars (`PRO_PRICE_STARS`, `CRYPTO_PAY_API_TOKEN`, `ADMIN_USER_ID`, …)
   - any tuning/guardrail vars you want to override
   *(Do **not** set a `PORT`; this is a worker, not a web service.)*
5. Deploy. Watch **Logs** for `Schema applied` then `Starting polling`.

### Monetization & persistence layer
- **Postgres** (asyncpg, no ORM) stores only durable data: users/quotas, Pro
  status, encrypted BYO keys, saved prompts, payments, and a media cache. The
  batch session stays in memory. `schema.sql` is applied idempotently on startup.
- **Free vs Pro:** free tier has a one-time signup bonus + daily audio/photo/LLM
  allowances; 🎨 images and 📊 presentations are Pro-only. Pro has cost-bounded
  daily caps and a bigger model/context. **BYO key** (`/setkey`) bypasses quotas.
- **Payments:** `/pro` offers Telegram **Stars** (native 30-day subscription) and
  **Crypto Pay** (USDT). Both record to `payments` and notify `ADMIN_USER_ID`.
- **Account commands:** `/usage`, `/pro`, `/setkey`, `/removekey`, `/prompts`,
  `/invite` (referrals), `/privacy`, `/forgetme` (deletes your data).

Because there's **no database/volume**, all state (batches, rate-limit
counters, FSM) resets on redeploy — that's expected and acceptable.

---

## Configuration reference

See [`.env.example`](.env.example) for every variable with comments. Highlights:

| Variable | Default | Purpose |
| --- | --- | --- |
| `DEBOUNCE_SECONDS` | `2.5` | Quiet time before a batch finalizes |
| `MAX_BATCH_MESSAGES` | `50` | Messages per batch (extras dropped) |
| `MAX_CONTEXT_CHARS` | `60000` | Cap on context sent to the LLM |
| `MAX_BATCHES_PER_HOUR` | `10` | Per-user batch rate limit |
| `MAX_LLM_CALLS_PER_DAY` | `50` | Per-user LLM-answer rate limit |
| `ALLOWED_USER_IDS` | *(empty)* | Allow-list; empty = public |
| `LINK_FETCH_TIMEOUT` | `15` | Timeout when fetching link context |

### A note on models
Model slugs on OpenRouter change over time. The defaults in `.env.example`
were the current matches as of 2026-06 for DeepSeek (text), Gemini Flash
(vision), Whisper Large v3 (transcription) and Gemini Flash Image
(`MODEL_IMAGE`) — **verify them at <https://openrouter.ai/models> before
deploying.** Because models are config-only, you can swap them without touching
code.

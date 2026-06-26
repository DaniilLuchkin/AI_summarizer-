-- Forwardly AI — durable data only (quotas, Pro, keys, prompts, payments, cache).
-- The in-memory session (batch buffer, debounce, assembled text, FSM) is NOT here.
-- All statements are idempotent so this file can run on every startup.

CREATE TABLE IF NOT EXISTS users (
  telegram_id      BIGINT PRIMARY KEY,
  lang_override    TEXT,
  pro_until        TIMESTAMPTZ,
  byo_key_enc      TEXT,                     -- Fernet-encrypted OpenRouter key
  bonus_audio_sec  INTEGER NOT NULL,         -- one-time signup pool, consumed first
  bonus_photos     INTEGER NOT NULL,
  referral_code    TEXT UNIQUE NOT NULL,
  referred_by      BIGINT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS usage_daily (
  telegram_id BIGINT NOT NULL,
  day         DATE NOT NULL,
  audio_sec   INTEGER NOT NULL DEFAULT 0,
  photos      INTEGER NOT NULL DEFAULT 0,
  llm_calls   INTEGER NOT NULL DEFAULT 0,
  images      INTEGER NOT NULL DEFAULT 0,
  pptx        INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (telegram_id, day)
);

CREATE TABLE IF NOT EXISTS media_cache (        -- saves OpenRouter cost on repeat files
  file_unique_id TEXT PRIMARY KEY,              -- Telegram's stable file_unique_id
  kind           TEXT NOT NULL,                 -- 'transcript' | 'vision'
  text           TEXT NOT NULL,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS saved_prompts (
  id          BIGSERIAL PRIMARY KEY,
  telegram_id BIGINT NOT NULL,
  title       TEXT NOT NULL,
  body        TEXT NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS payments (
  id          BIGSERIAL PRIMARY KEY,
  telegram_id BIGINT NOT NULL,
  provider    TEXT NOT NULL,                    -- 'stars' | 'crypto'
  amount      NUMERIC NOT NULL,
  currency    TEXT NOT NULL,                    -- 'XTR' | 'USDT' | 'TON'
  charge_id   TEXT,                             -- telegram_payment_charge_id or crypto invoice_id
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

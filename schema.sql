-- Forwardly AI — durable data only (quotas, Pro, keys, prompts, payments, cache).
-- The in-memory session (batch buffer, debounce, assembled text, FSM) is NOT here.
-- All statements are idempotent so this file can run on every startup.

CREATE TABLE IF NOT EXISTS users (
  telegram_id      BIGINT PRIMARY KEY,
  lang_override    TEXT,
  pro_until        TIMESTAMPTZ,
  byo_key_enc      TEXT,                     -- Fernet-encrypted OpenRouter key
  byo_active       BOOLEAN NOT NULL DEFAULT TRUE,  -- use stored key vs credits
  bonus_audio_sec  INTEGER NOT NULL DEFAULT 0,  -- legacy (pre-credits), unused
  bonus_photos     INTEGER NOT NULL DEFAULT 0,  -- legacy (pre-credits), unused
  referral_code    TEXT UNIQUE NOT NULL,
  referred_by      BIGINT,
  -- Credit balances stored as INTEGER TENTHS of a credit (1 credit = 10 units).
  credits              INTEGER NOT NULL DEFAULT 0,  -- persistent: bonus/referral/buy/Pro
  daily_credits        INTEGER NOT NULL DEFAULT 0,  -- daily free floor (reset, not added)
  daily_credits_date   DATE,
  signup_bonus_granted BOOLEAN NOT NULL DEFAULT FALSE,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Migrate existing deployments (idempotent; new columns + relaxed legacy NOTs).
ALTER TABLE users ADD COLUMN IF NOT EXISTS credits INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS daily_credits INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS daily_credits_date DATE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS signup_bonus_granted BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS byo_active BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE users ALTER COLUMN bonus_audio_sec SET DEFAULT 0;
ALTER TABLE users ALTER COLUMN bonus_photos SET DEFAULT 0;

-- Credit ledger: one row per grant/charge, delta in tenths.
CREATE TABLE IF NOT EXISTS credit_ledger (
  id          BIGSERIAL PRIMARY KEY,
  telegram_id BIGINT NOT NULL,
  delta       INTEGER NOT NULL,              -- tenths; + grant, - charge
  bucket      TEXT NOT NULL,                 -- 'persistent' | 'daily'
  reason      TEXT NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS credit_ledger_uid_idx ON credit_ledger (telegram_id, created_at);

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

CREATE TABLE IF NOT EXISTS user_models (   -- per-task model overrides (BYO-key users)
  telegram_id        BIGINT PRIMARY KEY,
  model_text         TEXT,                  -- NULL = use the global default for that slot
  model_vision       TEXT,
  model_transcribe   TEXT,
  model_image        TEXT,
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
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

"""Application configuration.

All runtime knobs come from environment variables (see `.env.example`).
We use `pydantic-settings` so values are parsed/validated once at startup and
then passed around as a typed object.
"""

from __future__ import annotations

from functools import cached_property

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # `protected_namespaces=()` silences pydantic's warning about fields that
    # start with "model_" (we intentionally name our model slug fields that way).
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=(),
    )

    # --- Required secrets -------------------------------------------------
    telegram_bot_token: str
    openrouter_api_key: str

    # --- OpenRouter endpoint / models ------------------------------------
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    model_text: str
    model_vision: str
    model_transcribe: str
    model_image: str

    # Attribution headers OpenRouter uses to identify the calling app.
    openrouter_app_title: str = "Telegram LLM Bot"
    openrouter_app_referer: str = "https://t.me"

    # --- Behaviour tuning -------------------------------------------------
    # How long to wait (seconds) after the last message before finalizing a batch.
    debounce_seconds: float = 2.5
    # Hard cap on messages collected into a single batch.
    max_batch_messages: int = 50
    # Cap on characters of context sent to the LLM (oldest items truncated).
    max_context_chars: int = 60000

    # --- Guardrails -------------------------------------------------------
    max_batches_per_hour: int = 10
    # Comma-separated Telegram user ids. Empty string == public (allow everyone).
    allowed_user_ids: str = ""

    # --- Link / file context ---------------------------------------------
    link_fetch_timeout: float = 15.0
    # Max characters kept from any single fetched link / parsed file.
    context_max_chars: int = 20000

    # --- Persistence / secrets -------------------------------------------
    # Railway Postgres plugin injects DATABASE_URL (postgresql://...). Required
    # for quotas/Pro/keys/prompts/payments to work.
    database_url: str = ""
    # urlsafe base64 32-byte Fernet key for encrypting BYO OpenRouter keys.
    # Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    app_secret: str = ""

    # --- Pro tier model / context ----------------------------------------
    model_text_pro: str = ""  # defaults to model_text when empty
    max_context_chars_pro: int = 120000

    # --- Presentations (deck planning + visual QA) -----------------------
    model_deck: str = ""       # strong planning model; defaults to text_model_pro
    model_qa_vision: str = ""  # QA defect detector; defaults to model_vision
    deck_qa_enabled: bool = True
    deck_qa_max_passes: int = 1   # detect->fix cycles (hard-capped at 2)
    deck_qa_max_slides: int = 15  # cap slides inspected by the vision QA

    # --- Billing ----------------------------------------------------------
    crypto_pay_api_token: str = ""  # empty -> hide crypto rail
    pro_price_stars: int = 250
    pro_price_usdt: float = 4.0
    pro_period_days: int = 30
    max_pro_purchases_per_day: int = 3
    admin_user_id: int = 0

    # --- Free tier quotas -------------------------------------------------
    free_signup_audio_sec: int = 600
    free_signup_photos: int = 5
    free_daily_audio_sec: int = 300
    free_daily_photos: int = 5
    free_daily_llm_calls: int = 30
    free_saved_prompts: int = 3

    # --- Pro tier quotas --------------------------------------------------
    pro_daily_audio_sec: int = 7200
    pro_daily_photos: int = 200
    pro_daily_llm_calls: int = 500
    pro_daily_images: int = 50
    pro_daily_pptx: int = 50

    # --- Referrals --------------------------------------------------------
    referral_bonus_audio_sec: int = 300
    referral_bonus_photos: int = 5

    # --- Group mode (in-memory thread buffer) ----------------------------
    group_buffer_max: int = 300          # messages kept per group chat
    group_buffer_ttl_hours: int = 24     # older messages are pruned
    group_summary_default: int = 50      # default N for /summary
    group_window_free: int = 80          # max messages summarized (free)
    group_window_pro: int = 400          # max messages summarized (Pro/BYO)
    group_cooldown_sec: int = 30         # min seconds between group LLM commands

    # --- Output rendering & streaming -------------------------------------
    # Stream the model's text answer live (SSE) via sendMessageDraft, falling
    # back to an edited placeholder message. Off -> just send the final answer.
    streaming_enabled: bool = True
    # Minimum gap (ms) between live draft/edit updates while streaming.
    stream_throttle_ms: int = 1000
    # Answers longer than this (chars) are sent as result.md instead of a long
    # chain of chat messages. Applies to everyone.
    long_answer_chars: int = 3500

    # --- Logging ----------------------------------------------------------
    log_level: str = "INFO"

    @property
    def text_model_pro(self) -> str:
        """Pro text model, falling back to the standard one if unset."""
        return self.model_text_pro or self.model_text

    @property
    def deck_model(self) -> str:
        """Strong deck-planning model, falling back to the Pro text model."""
        return self.model_deck or self.text_model_pro

    @property
    def qa_vision_model(self) -> str:
        """QA defect-detection vision model, falling back to the vision model."""
        return self.model_qa_vision or self.model_vision

    @cached_property
    def allowed_ids(self) -> set[int]:
        """Parse ALLOWED_USER_IDS into a set of ints. Empty set == public."""
        ids: set[int] = set()
        for chunk in self.allowed_user_ids.split(","):
            chunk = chunk.strip()
            if chunk:
                ids.add(int(chunk))
        return ids

    def is_user_allowed(self, user_id: int) -> bool:
        """Public bot when no allow-list is configured."""
        if not self.allowed_ids:
            return True
        return user_id in self.allowed_ids

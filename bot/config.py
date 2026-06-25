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
    max_llm_calls_per_day: int = 50
    # Comma-separated Telegram user ids. Empty string == public (allow everyone).
    allowed_user_ids: str = ""

    # --- Link / file context ---------------------------------------------
    link_fetch_timeout: float = 15.0
    # Max characters kept from any single fetched link / parsed file.
    context_max_chars: int = 20000

    # --- Logging ----------------------------------------------------------
    log_level: str = "INFO"

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

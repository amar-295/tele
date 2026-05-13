from pathlib import Path
from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Telegram ──────────────────────────────────────────────────────────────
    telegram_token:  str = Field(..., env="TELEGRAM_TOKEN")
    owner_chat_id:   int = Field(..., env="OWNER_CHAT_ID")
    # Webhook mode: set both to switch from long polling (HTTPS URL Telegram can reach).
    telegram_webhook_url: Optional[str] = Field(None, env="TELEGRAM_WEBHOOK_URL")
    telegram_webhook_secret: Optional[str] = Field(None, env="TELEGRAM_WEBHOOK_SECRET")
    webhook_listen: str = Field("0.0.0.0", env="WEBHOOK_LISTEN")
    # Render and many hosts inject PORT; used only in webhook mode.
    webhook_port: int = Field(8080, env="PORT")
    drop_pending_updates: bool = Field(False, env="DROP_PENDING_UPDATES")

    # ── Groq API (OpenAI-compatible) ──────────────────────────────────────────
    groq_api_key:  str = Field(..., env="GROQ_API_KEY")
    groq_model:    str = Field("llama-3.3-70b-versatile", env="GROQ_MODEL")
    groq_base_url: str = Field("https://api.groq.com/openai/v1", env="GROQ_BASE_URL")
    max_tokens:    int = Field(8192, env="MAX_TOKENS")

    # ── Memory / Vector Store ─────────────────────────────────────────────────
    chroma_path:    str = Field("./data/chroma", env="CHROMA_PATH")
    # How many Chroma hits to consider per collection before merge (raise if recall is thin).
    memory_top_k:   int = Field(8,               env="MEMORY_TOP_K")
    # Cosine distance cutoff for keeping a hit; lower = stricter (fewer, sharper memories).
    memory_threshold: float = Field(0.60, env="MEMORY_THRESHOLD")

    # ── Storage ───────────────────────────────────────────────────────────────
    db_path:   str = Field("./data/bot.db",  env="DB_PATH")
    logs_path: str = Field("./data/logs",    env="LOGS_PATH")

    # ── Pipeline ──────────────────────────────────────────────────────────────
    # Recent turns cap (before token trim); lower = cheaper, less conversational context.
    max_history_messages: int = Field(100,  env="MAX_HISTORY_MESSAGES")
    # Soft cap on history tokens (char/4 estimate); high default for personal use.
    max_history_tokens:   int = Field(64000, env="MAX_HISTORY_TOKENS")
    # Max facts injected into system prompt
    max_facts_in_prompt: int = Field(25, env="MAX_FACTS_IN_PROMPT")

    # ── Proactive digest (optional autonomy) ─────────────────────────────────
    # When true, sends periodic check-ins to OWNER_CHAT_ID (no extra API cost).
    proactive_digest_enabled: bool = Field(False, env="PROACTIVE_DIGEST_ENABLED")
    proactive_digest_interval_hours: float = Field(
        24.0, env="PROACTIVE_DIGEST_INTERVAL_HOURS"
    )

    class Config:
        env_file = ".env"

    @model_validator(mode="after")
    def _webhook_consistency(self) -> "Settings":
        url = (self.telegram_webhook_url or "").strip()
        if not url:
            object.__setattr__(self, "telegram_webhook_url", None)
            return self
        secret = (self.telegram_webhook_secret or "").strip()
        if not secret:
            raise ValueError(
                "TELEGRAM_WEBHOOK_SECRET is required when TELEGRAM_WEBHOOK_URL is set "
                "(Telegram sends it as header X-Telegram-Bot-Api-Secret-Token)."
            )
        object.__setattr__(self, "telegram_webhook_url", url)
        object.__setattr__(self, "telegram_webhook_secret", secret)
        return self


settings = Settings()

# Ensure all data directories exist on startup
for _p in [settings.chroma_path, Path(settings.db_path).parent, settings.logs_path]:
    Path(_p).mkdir(parents=True, exist_ok=True)

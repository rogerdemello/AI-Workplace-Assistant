from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import os
from pathlib import Path

# Determine project root (parent of backend/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:your-password@db.your-project.supabase.co:5432/postgres?sslmode=require"
    REDIS_URL: str = "redis://localhost:6379"
    AZURE_OPENAI_API_KEY: str = "mock-key"
    # Serve every model call from the deterministic in-process stub instead of
    # calling Azure. Intended for browser end-to-end runs: pointing them at an
    # unreachable endpoint means each turn pays the full retry timeout before
    # falling back, which makes the suite slow and timing-sensitive for reasons
    # that have nothing to do with the product. Default off; opt in explicitly.
    AI_USE_MOCK: bool = False
    AZURE_OPENAI_ENDPOINT: str = "https://mock.openai.azure.com"
    AZURE_OPENAI_DEPLOYMENT: str = "gpt-4"
    # Optional faster/cheaper deployment (e.g. gpt-4o-mini) used for streaming
    # general-chat replies to lower time-to-first-token. Falls back to
    # AZURE_OPENAI_DEPLOYMENT when empty.
    AZURE_OPENAI_FAST_DEPLOYMENT: str = ""
    AZURE_OPENAI_API_VERSION: str = "2024-12-01-preview"
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    MICROSOFT_CLIENT_ID: str = ""
    MICROSOFT_CLIENT_SECRET: str = ""
    VITE_API_URL: str = "http://localhost:8000"
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_USE_TLS: bool = True
    ENABLE_WHATSAPP_CHANNEL: bool = False
    # On by default — the agent only intercepts explicit weather / restaurant /
    # cafeteria keywords and falls back cleanly when no provider key is set
    # (weather works out of the box via open-meteo, no key required).
    ENABLE_LIFE_ASSISTANT: bool = True
    ENABLE_PRODUCTIVITY_AGENT: bool = False
    ENABLE_MULTI_AGENT_ORCHESTRATION: bool = False
    WHATSAPP_VERIFY_TOKEN: str = ""
    WHATSAPP_DEFAULT_USER_EMAIL: str = "emp1@mark.ai"
    WHATSAPP_USER_MAP: str = ""
    ENABLE_WHATSAPP_OUTBOUND: bool = False
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_WHATSAPP_FROM: str = ""
    # When true, validates X-Twilio-Signature on inbound /whatsapp/webhook hits.
    # Set false for local ngrok testing where URL rewriting breaks the HMAC.
    WHATSAPP_VALIDATE_SIGNATURE: bool = True

    # Microsoft Teams — Incoming Webhook for HR fan-out (alerts, patterns, etc.).
    # Create a webhook on the target channel ("Connectors" → "Incoming Webhook"),
    # paste the URL here, flip the flag, and posts go to that channel. Empty =
    # no-op (every Teams call returns False cleanly, the alert path is untouched).
    ENABLE_TEAMS_NOTIFICATIONS: bool = False
    TEAMS_WEBHOOK_URL: str = ""
    # Used in the "Open in MARK" deep link on the cards; falls back to no link
    # when empty.
    TEAMS_DASHBOARD_URL: str = ""

    LIFE_WEATHER_BASE_URL: str = "https://api.open-meteo.com/v1/forecast"
    LIFE_GEOCODE_BASE_URL: str = "https://geocoding-api.open-meteo.com/v1/search"
    LIFE_PLACES_API_URL: str = ""
    LIFE_PLACES_API_KEY: str = ""
    LIFE_CAFETERIA_MENU_JSON: str = ""
    # When true, skips heavy paths (lexicon-only sentiment in chat, fewer DB writes in tests).
    FAST_CHAT_MODE: bool = False
    # Chat API: use lexicon-only for synchronous sentiment (avoids hybrid LLM latency per turn).
    CHAT_SYNC_LEXICON_SENTIMENT: bool = True
    # Skip orchestrator intelligence LLM snapshot (saves one model call per message when MARK pipeline is on).
    CHAT_SKIP_INTELLIGENCE_SNAPSHOT: bool = True
    # Run wellbeing / memory side-effects after the HTTP response (faster TTFB on POST /chat/message).
    CHAT_DEFER_NONBLOCKING_SIDE_EFFECTS: bool = True
    SENTIMENT_STALE_DAYS: int = 7
    # Sustained negative sentiment: alert HR after N negative logs within a rolling window (not single-turn spikes).
    SUSTAINED_NEGATIVE_WINDOW_DAYS: int = 7
    SUSTAINED_NEGATIVE_MIN_MESSAGES: int = 3
    SUSTAINED_RISK_ALERT_COOLDOWN_HOURS: int = 24
    SUSTAINED_RISK_ALERTS_ENABLED: bool = True
    # Single-turn alerting (see sentiment_alerts.py). Scores are 0–100.
    # Alert when one message scores at or below this.
    SENTIMENT_ALERT_THRESHOLD: int = 30
    # Alert when conversation-level risk reaches or exceeds this.
    RISK_ALERT_THRESHOLD: int = 70
    # Minimum gap between alerts for the same employee, so HR isn't spammed.
    ALERT_COOLDOWN_MINUTES: int = 30
    # Comma-separated emotions that raise an alert on their own.
    EMOTION_ALERT_TRIGGERS: str = "burnout,exhaustion,betrayal,injustice,panic"
    # Hybrid sentiment: Azure chat JSON classifier first, lexicon fallback (see sentiment_llm.py).
    SENTIMENT_HYBRID_ENABLED: bool = True
    SENTIMENT_LLM_MAX_CHARS: int = 2000
    SENTIMENT_LLM_TIMEOUT_SECONDS: float = 12.0
    # When LLM and lexicon disagree (label or large score gap), blend scores with this LLM weight.
    SENTIMENT_BLEND_ON_DISAGREEMENT: bool = True
    SENTIMENT_BLEND_SCORE_GAP_THRESHOLD: float = 0.45
    SENTIMENT_BLEND_LLM_WEIGHT: float = 0.55
    # Employee-level score: blend last N message scores (0–100) into rolling aggregate (0 disables).
    SENTIMENT_ROLLING_TURNS: int = 5
    SENTIMENT_ROLLING_BLEND_WEIGHT: float = 0.25
    # Enhanced sentiment: context-aware, sarcasm detection, improved emotion detection
    USE_ENHANCED_SENTIMENT: bool = True
    # MARK intelligence — orchestrator LLM/lexicon snapshot → sentiment_logs + employee_scores
    ENABLE_MARK_INTELLIGENCE_PIPELINE: bool = True
    INTELLIGENCE_USE_LLM: bool = True
    INTELLIGENCE_ASYNC_QUEUE_ENABLED: bool = False

    # Employee Assistance Program resources surfaced when the bot detects distress.
    # JSON list of {label, url, description}; empty string falls back to safe defaults.
    EAP_RESOURCES_JSON: str = ""

    # IANA timezone used to compute "today" and "end of day" for daily-ritual
    # greetings when a user has no per-user timezone. Falls back to UTC if invalid.
    DEFAULT_DISPLAY_TIMEZONE: str = "Asia/Kolkata"
    # Local hour (0–23) at/after which the first chat of the day uses the
    # end-of-day wind-down opener instead of the morning check-in.
    WIND_DOWN_HOUR: int = 17

    # When true, proactive nudges that pass the rule-based suppression gate are
    # additionally checked by an LLM ("would this nudge help right now?").
    # Default off so behaviour is rule-only and no per-nudge LLM cost is incurred
    # until explicitly enabled. Fails open (allows the nudge) on any LLM error.
    NUDGE_AI_GATING_ENABLED: bool = False

    # ---- Data retention -------------------------------------------------
    # All disabled by default (0 = keep forever), because deleting employee
    # records is a decision for the business and its lawyers, not a default
    # someone inherits from a config file. See backend/docs/DATA_RETENTION.md.
    #
    # The useful shape is to expire the words while keeping the scores: HR
    # keeps the trends it acts on, and what an employee actually typed stops
    # existing. Nothing runs automatically — scripts/apply_retention.py does
    # the work, so deletion is always someone's explicit decision.
    RETENTION_CHAT_MESSAGES_DAYS: int = 0
    RETENTION_SENTIMENT_LOGS_DAYS: int = 0
    RETENTION_AUDIT_LOGS_DAYS: int = 0
    RETENTION_ANONYMOUS_FEEDBACK_DAYS: int = 0

    SUPABASE_URL: Optional[str] = None
    SUPABASE_SERVICE_KEY: Optional[str] = None
    SUPABASE_KEY: Optional[str] = None
    SUPABASE_JWT_SECRET: Optional[str] = None
    ALLOW_HEADER_ROLE_AUTH: bool = False

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

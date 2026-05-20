"""Optional Sentry wiring.

Both DSN and the SDK are optional. ``init_sentry`` is safe to call
unconditionally — it no-ops when ``SENTRY_DSN`` is unset or the SDK is not
installed, and it never raises.

Env vars:
  SENTRY_DSN              required to enable
  SENTRY_ENVIRONMENT      defaults to "development"
  SENTRY_TRACES_SAMPLE_RATE   float 0.0–1.0, defaults to 0.1
  SENTRY_RELEASE          optional release tag
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def init_sentry() -> bool:
    """Initialize Sentry if configured. Returns True when Sentry is active."""
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    except ImportError:
        logger.warning("SENTRY_DSN set but sentry-sdk is not installed; skipping init")
        return False

    try:
        sample_rate = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1"))
    except ValueError:
        sample_rate = 0.1

    try:
        sentry_sdk.init(
            dsn=dsn,
            environment=os.getenv("SENTRY_ENVIRONMENT", "development"),
            release=os.getenv("SENTRY_RELEASE") or None,
            traces_sample_rate=sample_rate,
            send_default_pii=False,
            integrations=[FastApiIntegration(), SqlalchemyIntegration()],
        )
    except Exception:
        logger.exception("Sentry initialization failed (non-fatal)")
        return False

    logger.info("Sentry initialized (environment=%s)", os.getenv("SENTRY_ENVIRONMENT", "development"))
    return True

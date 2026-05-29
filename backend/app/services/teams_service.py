"""Microsoft Teams Incoming Webhook adapter.

Per-user OAuth isn't worth it for an HR fan-out — Teams admins can create an
Incoming Webhook for a shared channel ("#hr-alerts") in two clicks. Set
TEAMS_WEBHOOK_URL and ENABLE_TEAMS_NOTIFICATIONS=true and these calls become
real posts; leave them empty and everything no-ops cleanly so nothing in the
alert path breaks for environments that don't use Teams.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from ..config import settings

logger = logging.getLogger(__name__)


_SEVERITY_COLORS = {
    "high": "D93025",      # red
    "critical": "B7081B",  # deeper red
    "medium": "F59E0B",    # amber
    "warning": "F59E0B",
    "low": "3B82F6",       # blue
    "info": "3B82F6",
}


def is_enabled() -> bool:
    """True when both the flag and the webhook URL are set."""
    return bool(settings.ENABLE_TEAMS_NOTIFICATIONS) and bool((settings.TEAMS_WEBHOOK_URL or "").strip())


def _build_message_card(
    *,
    title: str,
    body: str,
    severity: str,
    dashboard_url: Optional[str],
) -> dict:
    color = _SEVERITY_COLORS.get(severity.lower(), "3B82F6")
    card: dict = {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "summary": title or "MARK notification",
        "themeColor": color,
        "title": title,
        "text": body,
    }
    if dashboard_url:
        card["potentialAction"] = [
            {
                "@type": "OpenUri",
                "name": "Open in MARK",
                "targets": [{"os": "default", "uri": dashboard_url}],
            }
        ]
    return card


def post_message(
    *,
    title: str,
    body: str,
    severity: str = "info",
    dashboard_url: Optional[str] = None,
    timeout_seconds: float = 6.0,
) -> bool:
    """Post a MessageCard to the configured Incoming Webhook.

    No-ops cleanly when Teams isn't configured. Returns True on success, False
    on any failure (logged but never raised — never break the calling path).
    """
    if not is_enabled():
        return False
    url = (settings.TEAMS_WEBHOOK_URL or "").strip()
    payload = _build_message_card(
        title=title, body=body, severity=severity, dashboard_url=dashboard_url,
    )
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.post(url, json=payload)
        ok = 200 <= response.status_code < 300
        if not ok:
            logger.warning("Teams webhook returned %s: %s", response.status_code, response.text[:200])
        return ok
    except Exception:
        logger.warning("Teams webhook post failed", exc_info=True)
        return False


def notify_hr_alert(
    *,
    title: str,
    body: str,
    severity: str = "medium",
    dashboard_url: Optional[str] = None,
) -> bool:
    """High-level convenience for HR alerts (sustained risk, sentiment drop, etc.)."""
    return post_message(
        title=f"⚠ {title}" if severity in ("high", "critical") else title,
        body=body,
        severity=severity,
        dashboard_url=dashboard_url,
    )


def notify_pattern(
    *,
    pattern_label: str,
    recommendation: str,
    severity: str = "medium",
    dashboard_url: Optional[str] = None,
) -> bool:
    """Surface a detected cross-employee pattern with its recommended action."""
    return post_message(
        title=pattern_label,
        body=f"**Recommendation:** {recommendation}",
        severity=severity,
        dashboard_url=dashboard_url,
    )

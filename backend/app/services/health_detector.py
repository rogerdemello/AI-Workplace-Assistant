"""
Health Detector Service - Detects health-related keywords in user messages.

This module provides lightweight keyword-based health detection
for triggering follow-up actions when users mention being unwell.
"""

from __future__ import annotations

from typing import Any, Dict, List


# Health-related keywords for detection
HEALTH_KEYWORDS = [
    "fever",
    "sick",
    "not feeling well",
    "headache",
    "migraine",
    "flu",
    "cold",
    "unwell",
    "ill",
    "nausea",
    "dizzy",
    "tired",
    "exhausted",
]


def detect_health_keywords(message: str) -> Dict[str, Any]:
    """
    Detect health-related keywords in a message and return analysis result.

    Args:
        message: The user message to analyze.

    Returns:
        Dictionary containing:
            - has_health_concern: bool indicating if health concerns were detected
            - keywords: List[str] of detected health keywords
            - severity: str severity level ('high', 'medium', 'low', or 'none')
    """
    if not message:
        return {
            "has_health_concern": False,
            "keywords": [],
            "severity": "none",
        }

    lowered = message.lower()
    detected = [kw for kw in HEALTH_KEYWORDS if kw in lowered]

    has_concern = len(detected) > 0

    # Determine severity based on number of keywords found
    if has_concern:
        count = len(detected)
        if count >= 3:
            severity = "high"
        elif count >= 2:
            severity = "medium"
        else:
            severity = "low"
    else:
        severity = "none"

    return {
        "has_health_concern": has_concern,
        "keywords": detected,
        "severity": severity,
    }


__all__ = [
    "HEALTH_KEYWORDS",
    "detect_health_keywords",
]
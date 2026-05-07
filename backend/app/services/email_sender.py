from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from typing import Iterable


class EmailSenderError(RuntimeError):
    """Raised when SMTP delivery cannot be completed."""


def _smtp_config() -> tuple[str, int, str, str, str, bool]:
    host = os.getenv("SMTP_HOST", "").strip()
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()
    from_email = os.getenv("SMTP_FROM_EMAIL", username).strip()
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() in ("1", "true", "yes")
    if not host or not from_email:
        raise EmailSenderError("SMTP is not configured. Set SMTP_HOST and SMTP_FROM_EMAIL.")
    return host, port, username, password, from_email, use_tls


def send_email_via_smtp(*, to: str, subject: str, body: str, cc: Iterable[str] | None = None) -> None:
    host, port, username, password, from_email, use_tls = _smtp_config()
    recipients = [to] + [item for item in (cc or []) if item]

    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = to
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        with smtplib.SMTP(host, port, timeout=20) as smtp:
            smtp.ehlo()
            if use_tls:
                smtp.starttls()
                smtp.ehlo()
            if username and password:
                smtp.login(username, password)
            smtp.send_message(msg, to_addrs=recipients)
    except Exception as exc:  # pragma: no cover
        raise EmailSenderError(f"SMTP send failed: {exc}") from exc

"""Column-level encryption helpers (Fernet / AES-GCM via ``cryptography``).

Designed for dedicated-deployment customers who need at-rest encryption for
sensitive free-text fields — complaint bodies, internal HR notes, sentiment
narratives. The Fernet key is sourced from the ``MARK_ENCRYPTION_KEY`` env
var (URL-safe base64-encoded 32-byte key).

Generate a key on a new deployment::

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

This module is opt-in — until you swap a column type to ``EncryptedText``,
nothing about persisted data changes. Existing values stay readable.

Migration playbook (when you do migrate a column):
  1. Add the env var to the new deployment.
  2. Change ``Column(Text)`` → ``Column(EncryptedText)`` on the model.
  3. Write a one-time backfill script that loads each row, re-saves it (SQLAlchemy
     will encrypt on write), and commits in batches.
  4. Verify reads, then keep the old plaintext column around for one release
     before dropping it.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Optional

from sqlalchemy import String
from sqlalchemy.types import TypeDecorator

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_fernet():
    """Return a Fernet instance, or None if no key is configured.

    Cached so we don't re-derive the key on every column access. The cache is
    fine for the lifetime of the process — keys are not expected to rotate
    while the API is running; a rotation requires a deploy and a re-encrypt
    pass anyway.
    """
    key = (os.getenv("MARK_ENCRYPTION_KEY") or "").strip()
    if not key:
        return None
    try:
        from cryptography.fernet import Fernet  # type: ignore

        return Fernet(key.encode("utf-8") if isinstance(key, str) else key)
    except Exception:
        logger.exception("MARK_ENCRYPTION_KEY is set but Fernet initialization failed")
        return None


def is_encryption_active() -> bool:
    return _get_fernet() is not None


def encrypt_str(plaintext: Optional[str]) -> Optional[str]:
    """Encrypt a string. Returns the original when encryption is disabled.

    Caller is responsible for storing the returned token verbatim. Empty
    strings and ``None`` round-trip unchanged.
    """
    if plaintext is None or plaintext == "":
        return plaintext
    fernet = _get_fernet()
    if fernet is None:
        return plaintext
    return fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_str(token: Optional[str]) -> Optional[str]:
    """Decrypt a token produced by ``encrypt_str``. Tolerates plaintext input
    so existing rows stay readable until a backfill happens."""
    if token is None or token == "":
        return token
    fernet = _get_fernet()
    if fernet is None:
        return token
    try:
        return fernet.decrypt(token.encode("ascii")).decode("utf-8")
    except Exception:
        # Likely a pre-encryption plaintext row. Return as-is so reads don't
        # break during the in-flight migration.
        return token


class EncryptedText(TypeDecorator):
    """A SQLAlchemy column type that transparently encrypts on write and
    decrypts on read. Stored as a TEXT-equivalent string in the database.

    Usage::

        from app.core.encryption import EncryptedText

        class Ticket(Base):
            internal_notes = Column(EncryptedText, nullable=True)
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):  # noqa: D401 — SA contract
        return encrypt_str(value)

    def process_result_value(self, value, dialect):  # noqa: D401 — SA contract
        return decrypt_str(value)

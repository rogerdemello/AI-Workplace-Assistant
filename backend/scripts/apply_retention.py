"""Delete employee data past its retention period.

MARK stores what people say when they are struggling: chat messages naming
colleagues, medical reasons on leave requests, appointment topics they would not
raise with their manager. Held indefinitely that stops being a service and
becomes a liability — the longer it exists, the more likely it is read by
someone the employee never intended.

Nothing here runs on a schedule. Deletion is irreversible and the periods are a
legal and business decision, so it is always a person running a command, having
read what it is about to remove. Every period defaults to 0 (keep forever), so
this script does nothing at all until someone configures it.

Usage::

    python -m scripts.apply_retention --dry-run     # always start here
    python -m scripts.apply_retention --confirm

Periods come from settings (see docs/DATA_RETENTION.md):

    RETENTION_CHAT_MESSAGES_DAYS        what employees typed
    RETENTION_SENTIMENT_LOGS_DAYS       derived per-message scores
    RETENTION_AUDIT_LOGS_DAYS           request audit trail (hashes, no bodies)
    RETENTION_ANONYMOUS_FEEDBACK_DAYS   anonymous submissions

The intended shape is to expire chat text well before the derived signals: HR
keeps the trends it acts on while the employee's actual words stop existing.
"""

from __future__ import annotations

import argparse
from datetime import timedelta
from typing import List, Tuple

from sqlalchemy import func

from app.config import settings
from app.core.time import utcnow_naive
from app.database import SessionLocal
from app.models.anonymous_feedback import AnonymousFeedback
from app.models.audit_log import AuditLog
from app.models.conversation import Message
from app.models.sentiment_log import SentimentLog


def _policies() -> List[Tuple[str, object, object, int]]:
    """(label, model, timestamp column, retention days) for each configured rule."""
    return [
        ("chat messages", Message, Message.created_at, settings.RETENTION_CHAT_MESSAGES_DAYS),
        ("sentiment logs", SentimentLog, SentimentLog.created_at, settings.RETENTION_SENTIMENT_LOGS_DAYS),
        ("audit logs", AuditLog, AuditLog.created_at, settings.RETENTION_AUDIT_LOGS_DAYS),
        (
            "anonymous feedback",
            AnonymousFeedback,
            AnonymousFeedback.created_at,
            settings.RETENTION_ANONYMOUS_FEEDBACK_DAYS,
        ),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="count only, delete nothing")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="actually delete. Required — there is no accidental path to deletion.",
    )
    args = parser.parse_args()

    if not args.dry_run and not args.confirm:
        print("Refusing to run without --dry-run or --confirm.")
        print("Deletion is irreversible; start with --dry-run.")
        return 2

    db = SessionLocal()
    try:
        configured = [p for p in _policies() if p[3] and p[3] > 0]
        if not configured:
            print("No retention periods configured — nothing to do.")
            print("Every RETENTION_*_DAYS is 0 (keep forever). This is the default:")
            print("the periods are a business decision, see docs/DATA_RETENTION.md.")
            return 0

        now = utcnow_naive()
        total = 0
        for label, model, column, days in configured:
            cutoff = now - timedelta(days=days)
            count = db.query(func.count()).select_from(model).filter(column < cutoff).scalar() or 0
            total += count
            verb = "would delete" if args.dry_run else "deleting"
            print(f"{label:22} keep {days:>5}d  {verb} {count} rows older than {cutoff:%Y-%m-%d}")
            if not args.dry_run and count:
                db.query(model).filter(column < cutoff).delete(synchronize_session=False)

        if args.dry_run:
            print(f"\ndry run — {total} rows would be deleted, nothing changed")
            return 0

        db.commit()
        print(f"\ndeleted {total} rows")
        # Scores are recomputed from sentiment_logs, so expiring chat text does
        # not disturb the dashboards. Expiring sentiment_logs does: those
        # aggregates will drift on the next recompute, which is the intended
        # trade and worth saying out loud.
        if settings.RETENTION_SENTIMENT_LOGS_DAYS:
            print("note: sentiment logs were pruned; employee aggregates will")
            print("      shift on their next recompute.")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

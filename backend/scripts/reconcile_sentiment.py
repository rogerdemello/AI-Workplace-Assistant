"""Reprocess employee messages that never reached sentiment_logs.

The sentiment pipeline is best-effort: if it fails — a database blip, a model
outage, a deploy mid-request — the chat reply still succeeds and the message is
saved, but the signal never reaches the HR dashboard. `/metrics` counts those
failures (`sentiment_pipeline_failures_total`), and until now that was the end
of it. The employee's message existed; the fact that they were struggling did
not.

This finds user messages with no sentiment log and processes them. Safe to run
repeatedly: `_log_sentiment` skips messages that already have a row, and a
partial unique index enforces it in the database.

Usage::

    python -m scripts.reconcile_sentiment --days 7 --dry-run
    python -m scripts.reconcile_sentiment --days 7

Run it after any incident that shows up in sentiment_pipeline_failures_total,
and periodically if you want the dashboards to be trustworthy rather than
mostly-right.
"""

from __future__ import annotations

import argparse
import sys
from datetime import timedelta

from sqlalchemy import and_, func, select

from app.core.time import utcnow_naive
from app.database import SessionLocal
from app.models.conversation import Conversation, Message, MessageSender
from app.models.sentiment_log import SentimentLog
from app.services.sentiment import SentimentService
from app.services.sentiment_pipeline import SentimentPipelineService


def find_unprocessed(db, days: int, limit: int):
    """User messages inside the window with no sentiment log."""
    cutoff = utcnow_naive() - timedelta(days=days)
    logged = select(SentimentLog.message_id).where(SentimentLog.message_id.isnot(None))
    return (
        db.query(Message, Conversation.user_id)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .filter(
            and_(
                Message.sender == MessageSender.user,
                Message.created_at >= cutoff,
                Message.id.notin_(logged),
            )
        )
        .order_by(Message.created_at.asc())
        .limit(limit)
        .all()
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=7, help="how far back to look")
    parser.add_argument("--limit", type=int, default=1000, help="max messages per run")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would be processed, change nothing",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        total_messages = (
            db.query(func.count(Message.id))
            .join(Conversation, Message.conversation_id == Conversation.id)
            .filter(
                Message.sender == MessageSender.user,
                Message.created_at >= utcnow_naive() - timedelta(days=args.days),
            )
            .scalar()
            or 0
        )
        pending = find_unprocessed(db, args.days, args.limit)

        print(f"window            : last {args.days} days")
        print(f"user messages     : {total_messages}")
        print(f"missing a log     : {len(pending)}")
        if total_messages:
            covered = 100.0 * (total_messages - len(pending)) / total_messages
            print(f"coverage          : {covered:.1f}%")

        if not pending:
            print("nothing to reconcile")
            return 0
        if args.dry_run:
            print("dry run — nothing written")
            return 0

        sentiment = SentimentService(db)
        pipeline = SentimentPipelineService(db)
        repaired = failed = 0

        for message, employee_id in pending:
            try:
                result = sentiment.analyze(message.message_text or "")
                pipeline.process_message(
                    employee_id=employee_id,
                    message_id=message.id,
                    message_text=message.message_text or "",
                    sentiment_label=str(result.get("sentiment", "neutral")),
                    sentiment_score=float(result.get("score", 0.0) or 0.0),
                    conversation_id=message.conversation_id,
                )
                repaired += 1
            except Exception as exc:  # keep going; one bad row must not stop the run
                failed += 1
                print(f"  failed {message.id}: {type(exc).__name__}: {exc}", file=sys.stderr)
                db.rollback()

        print(f"reconciled        : {repaired}")
        if failed:
            print(f"still failing     : {failed}")
            print("re-run after investigating; already-repaired rows are skipped")
        return 1 if failed else 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

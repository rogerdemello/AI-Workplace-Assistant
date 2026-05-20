"""Celery tasks that defer slow / IO-bound work off the request path.

Three tasks today, all opt-in via ``CELERY_BROKER_URL``:

  * :func:`process_sentiment_for_message` — pulls a saved Message and runs
    the sentiment + intelligence pipeline against it. Caller saves the
    Message first, then enqueues this with just the message id.
  * :func:`run_proactive_wellbeing_scan` — same daily scan today's main.py
    background loop runs. Wrapping it lets schedulers (APScheduler, Celery
    beat, k8s cron) trigger it without owning the implementation.
  * :func:`deliver_webhook` — single best-effort delivery for one webhook.
    ``WebhookService.trigger_webhook`` fans out to all matching webhooks
    serially today; with this task we can dispatch each delivery to its own
    worker slot.

Each task opens its own DB session and closes it — workers and request
handlers must not share sessions.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional
from uuid import UUID

from .celery_app import celery


logger = logging.getLogger(__name__)


@celery.task(name="mark.process_sentiment_for_message", bind=True, max_retries=2)
def process_sentiment_for_message(self, message_id: str) -> Dict[str, Any]:
    """Run the sentiment pipeline against a previously-saved Message.

    Returns a small status dict for logging. The pipeline writes
    ``sentiment_logs`` / ``employee_scores`` directly — no value needs to
    flow back to the API caller.
    """
    from ..database import SessionLocal
    from ..models.conversation import Message
    from ..services.sentiment_pipeline import SentimentPipelineService

    db = SessionLocal()
    try:
        message = db.query(Message).filter(Message.id == UUID(message_id)).first()
        if message is None:
            logger.info("process_sentiment_for_message: message %s missing", message_id)
            return {"status": "missing", "message_id": message_id}

        conversation = message.conversation
        if conversation is None or conversation.user_id is None:
            return {"status": "no_user", "message_id": message_id}

        pipeline = SentimentPipelineService(db)
        result = pipeline.process_message(
            employee_id=conversation.user_id,
            message_id=message.id,
            message_text=message.message_text or "",
            sentiment_label=getattr(message.sentiment, "value", None) if message.sentiment else None,
            conversation_id=conversation.id,
        )
        return {"status": "ok", "message_id": message_id, "score": result.get("score_0_100")}
    except Exception as exc:
        logger.exception("Sentiment pipeline failed for message %s", message_id)
        # Retry once with backoff — transient DB / LLM hiccups are common.
        raise self.retry(exc=exc, countdown=15) from exc
    finally:
        db.close()


@celery.task(name="mark.run_proactive_wellbeing_scan")
def run_proactive_wellbeing_scan() -> Dict[str, Any]:
    """Run the daily proactive wellbeing scan that materialises ``hr_alerts``."""
    from ..database import SessionLocal
    from ..api.v1.hr_alerts import _store_from_wellbeing

    db = SessionLocal()
    try:
        count = _store_from_wellbeing(db)
        return {"status": "ok", "alerts_created": int(count or 0)}
    except Exception:
        logger.exception("Proactive wellbeing scan failed")
        db.rollback()
        return {"status": "error"}
    finally:
        db.close()


@celery.task(name="mark.deliver_webhook", bind=True, max_retries=3, default_retry_delay=30)
def deliver_webhook(
    self,
    webhook_id: str,
    event_type: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Deliver one webhook. Retries on transient HTTP failures."""
    from ..database import SessionLocal
    from ..models.webhook import Webhook
    from ..services.webhook_service import WebhookService

    db = SessionLocal()
    try:
        webhook = db.query(Webhook).filter(Webhook.id == UUID(webhook_id)).first()
        if webhook is None:
            return {"status": "missing", "webhook_id": webhook_id}

        service = WebhookService(db)
        # ``_deliver_webhook`` is the private synchronous variant the existing
        # service uses internally; calling it here keeps signature + retry
        # accounting identical to the in-process path.
        delivery = service._deliver_webhook(webhook, event_type, payload)
        return {
            "status": "ok",
            "webhook_id": webhook_id,
            "delivery_id": str(delivery.id) if delivery else None,
        }
    except Exception as exc:
        logger.warning("Webhook delivery %s failed; retrying", webhook_id, exc_info=True)
        raise self.retry(exc=exc) from exc
    finally:
        db.close()


__all__ = [
    "process_sentiment_for_message",
    "run_proactive_wellbeing_scan",
    "deliver_webhook",
]

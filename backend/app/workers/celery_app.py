"""Celery app + a thin ``enqueue`` helper that works without a broker.

The Celery app object only matters when ``CELERY_BROKER_URL`` is set — the
``enqueue`` helper checks the env var and either ``.delay()`` for real workers
or calls the task body inline. That keeps the single-process deployment path
identical to the pre-Celery world while making the multi-worker path a single
env-var flip away.

Boot a worker with::

    cd backend
    celery -A app.workers.celery_app.celery worker -l info -Q default

The worker process needs the same Python env + DATABASE_URL etc. as the API.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable

from celery import Celery


logger = logging.getLogger(__name__)


def _broker_url() -> str | None:
    raw = os.getenv("CELERY_BROKER_URL", "").strip()
    return raw or None


# Single Celery app the API and the worker share. When no broker is configured
# the object still exists so ``@celery.task`` decorators don't blow up at import
# time; calls always go inline via :func:`enqueue`.
celery = Celery(
    "mark",
    broker=_broker_url() or "memory://",
    backend=os.getenv("CELERY_RESULT_BACKEND") or None,
    include=["app.workers.tasks"],
)

celery.conf.update(
    task_default_queue="default",
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Don't auto-retry forever — let task-level decorators decide. Avoids
    # silent infinite loops when a downstream service is down.
    task_default_retry_delay=30,
)


def has_broker() -> bool:
    return _broker_url() is not None


def enqueue(task: Any, *args: Any, **kwargs: Any) -> Any:
    """Send a Celery task to the broker, or run it inline when no broker is set.

    Returns whatever ``.delay()`` would (an AsyncResult) when a broker is
    configured; otherwise returns the task's actual return value. Callers
    treat the return value as fire-and-forget — none of the wrapped tasks
    surface results back to request handlers.
    """
    if has_broker():
        try:
            return task.delay(*args, **kwargs)
        except Exception:
            logger.exception("Celery enqueue failed; falling back to inline execution")
    # Inline fallback. ``task.run`` is Celery's underlying function — same
    # callable the worker would invoke. We deliberately *do not* use
    # ``.apply()`` because that wraps the result in an EagerResult, which
    # the caller doesn't want here.
    return task.run(*args, **kwargs)

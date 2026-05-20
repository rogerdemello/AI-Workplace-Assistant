"""Async worker layer for MARK.

Opt-in via the ``CELERY_BROKER_URL`` env var. When unset the helpers in
``celery_app.py`` fall back to inline execution so single-process deployments
keep working unchanged — Celery is a deployment knob, not a hard dependency.
"""

"""Boot-time schema audit.

We currently create tables via ``Base.metadata.create_all`` on startup for dev
convenience, but Alembic migrations also exist. Without a periodic check, the
two paths drift silently: a new migration is added but never applied, and the
running schema diverges from what models expect.

This module logs a loud WARN when:
  * The DB has tables but no ``alembic_version`` row (never been stamped).
  * The stamped revision is behind the latest migration file on disk.

It never mutates the DB. Remediation is manual::

    cd backend && alembic stamp head            # if schema matches head
    cd backend && alembic upgrade head          # to apply pending migrations
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


_ALEMBIC_DIR = Path(__file__).resolve().parent.parent.parent / "alembic"


def _latest_revision_on_disk() -> Optional[str]:
    """Return the alembic head revision id, or None if alembic is misconfigured."""
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        ini_path = _ALEMBIC_DIR.parent / "alembic.ini"
        if not ini_path.exists():
            return None
        cfg = Config(str(ini_path))
        cfg.set_main_option("script_location", str(_ALEMBIC_DIR))
        script = ScriptDirectory.from_config(cfg)
        heads = script.get_heads()
        if not heads:
            return None
        # Multiple heads = branched migrations; surface as None so we warn explicitly.
        return heads[0] if len(heads) == 1 else None
    except Exception:
        return None


def _stamped_revision(engine: Engine) -> Optional[str]:
    """Return the revision id in ``alembic_version``, or None if the table is missing."""
    try:
        inspector = inspect(engine)
        if "alembic_version" not in inspector.get_table_names():
            return None
        with engine.connect() as conn:
            row = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).first()
            return row[0] if row else None
    except Exception:
        return None


def _db_has_tables(engine: Engine) -> bool:
    try:
        inspector = inspect(engine)
        return any(t != "alembic_version" for t in inspector.get_table_names())
    except Exception:
        return False


def audit_schema(engine: Engine, logger: logging.Logger) -> None:
    """Log a warning when the DB schema and alembic migrations are out of sync.

    SQLite is skipped — local dev runs ``create_all`` and doesn't need migrations.
    """
    try:
        if engine.dialect.name == "sqlite":
            return

        latest = _latest_revision_on_disk()
        stamped = _stamped_revision(engine)
        has_tables = _db_has_tables(engine)

        if latest is None:
            logger.warning(
                "schema_audit: could not determine alembic head from %s — skipping check",
                _ALEMBIC_DIR,
            )
            return

        if stamped is None:
            if has_tables:
                logger.warning(
                    "schema_audit: DB has tables but no alembic_version row. "
                    "Run `alembic stamp %s` from backend/ to baseline migrations.",
                    latest,
                )
            else:
                logger.info("schema_audit: empty DB; create_all() will materialize schema")
            return

        if stamped != latest:
            logger.warning(
                "schema_audit: DB stamped at %s but latest migration is %s. "
                "Run `alembic upgrade head` from backend/ to apply pending changes.",
                stamped,
                latest,
            )
        else:
            logger.info("schema_audit: schema in sync with alembic head %s", latest)
    except Exception:
        logger.exception("schema_audit: unexpected error during audit (non-fatal)")

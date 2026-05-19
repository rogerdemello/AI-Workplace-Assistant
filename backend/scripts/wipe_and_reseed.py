"""
Surgical cleanup: keep only the two login users, delete every other user and
the rows that reference them. Schema, departments, RAG documents, automation
rules, and any non-user-scoped data are preserved.

Keeps:
  - HR:        hr1@mark.ai   / password123
  - Employee:  emp1@mark.ai  / password123

Run from the `backend` directory:

  python -m scripts.wipe_and_reseed
"""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import app.models  # noqa: F401  — register all models with Base.metadata
from sqlalchemy import text

from app.database import Base, engine, SessionLocal
from app.models.user import User
from scripts.seed_dummy_users import seed as seed_two_users

KEEP_EMAILS = {"hr1@mark.ai", "emp1@mark.ai"}


def _user_referencing_tables(conn) -> list[tuple[str, str]]:
    """Find every (table, column) that has a FK pointing at users.id.

    Postgres path uses information_schema; SQLite path falls back to a
    hand-maintained list (mirrors the SQLAlchemy models in app/models).
    """
    dialect = engine.dialect.name
    if dialect == "postgresql":
        result = conn.execute(text("""
            SELECT
              tc.table_name AS referencing_table,
              kcu.column_name AS referencing_column
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
              ON ccu.constraint_name = tc.constraint_name
             AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND ccu.table_name = 'users'
              AND ccu.column_name = 'id'
              AND tc.table_schema = 'public'
        """))
        return [(row[0], row[1]) for row in result]

    # SQLite fallback: hard-coded list matching app/models.
    return [
        ("conversations", "user_id"),
        ("tickets", "user_id"),
        ("tickets", "assigned_to"),
        ("ticket_action_logs", "actor_id"),
        ("sentiment_logs", "user_id"),
        ("employee_scores", "user_id"),
        ("risk_snapshots", "user_id"),
        ("leave_requests", "user_id"),
        ("leave_requests", "approved_by"),
        ("hr_alerts", "user_id"),
        ("hr_notifications", "user_id"),
        ("mood_entries", "user_id"),
        ("reminder_schedules", "user_id"),
        ("activity_events", "user_id"),
        ("automation_actions", "user_id"),
        ("automation_rules", "created_by"),
        ("wellbeing_signals", "user_id"),
        ("onboarding_checklists", "user_id"),
        ("onboarding_buddies", "user_id"),
        ("onboarding_buddies", "buddy_id"),
        ("meeting_events", "user_id"),
        ("room_bookings", "user_id"),
        ("calendar_integrations", "user_id"),
        ("chat_feedback", "user_id"),
        ("celebrations", "user_id"),
        ("appreciation_notes", "sender_id"),
        ("appreciation_notes", "recipient_id"),
        ("personal_facts", "user_id"),
        ("conversation_memory", "user_id"),
        ("attachments", "user_id"),
        ("webhooks", "created_by"),
        ("survey_responses", "user_id"),
        ("surveys", "created_by"),
        ("user_profiles", "user_id"),
        ("documents", "uploaded_by"),
        ("users", "manager_id"),  # self-FK
    ]


def _in_clause(ids: list[str]) -> tuple[str, dict]:
    """Build a portable IN (...) clause and the matching named-parameter dict.

    Works for both Postgres (UUIDs as strings — Postgres auto-casts when the
    column is uuid and the literal is in an IN list) and SQLite.
    """
    if not ids:
        return "(NULL)", {}
    placeholders = ", ".join(f":p{i}" for i in range(len(ids)))
    params = {f"p{i}": uid for i, uid in enumerate(ids)}
    return f"({placeholders})", params


def _run(sql: str, params: dict, label: str, deleted: dict[str, int]) -> None:
    """Execute one DELETE in its own transaction so a failure on table X doesn't
    poison the transaction for table Y (Postgres aborts the whole tx on error)."""
    try:
        with engine.begin() as conn:
            r = conn.execute(text(sql), params)
            deleted[label] = (deleted.get(label, 0) + (r.rowcount or 0))
    except Exception as exc:
        msg = str(exc).split("\n")[0][:120]
        print(f"  (skipped {label}: {msg})", file=sys.stderr)


def _delete_cascade_for_users(extra_ids: list[str]) -> dict[str, int]:
    """For each user-referencing FK, delete rows where the FK column matches extra_ids."""
    if not extra_ids:
        return {}

    deleted: dict[str, int] = {}
    in_clause, base_params = _in_clause(extra_ids)

    # Look up dependent rows once (need a successful tx).
    with engine.begin() as conn:
        refs = _user_referencing_tables(conn)
        try:
            conv_ids = [str(row[0]) for row in conn.execute(
                text(f"SELECT id FROM conversations WHERE user_id IN {in_clause}"), base_params,
            )]
        except Exception:
            conv_ids = []
        try:
            tic_ids = [str(row[0]) for row in conn.execute(
                text(f"SELECT id FROM tickets WHERE user_id IN {in_clause}"), base_params,
            )]
        except Exception:
            tic_ids = []

    # 1. message_signals → messages → conversation
    if conv_ids:
        conv_in, conv_params = _in_clause(conv_ids)
        _run(
            f'DELETE FROM message_signals WHERE message_id IN '
            f'(SELECT id FROM messages WHERE conversation_id IN {conv_in})',
            conv_params, "message_signals", deleted,
        )
        _run(
            f"DELETE FROM messages WHERE conversation_id IN {conv_in}",
            conv_params, "messages", deleted,
        )

    # 2. ticket_messages / ticket_action_logs → tickets
    if tic_ids:
        tic_in, tic_params = _in_clause(tic_ids)
        _run(f'DELETE FROM ticket_messages WHERE ticket_id IN {tic_in}', tic_params, "ticket_messages", deleted)
        _run(f'DELETE FROM ticket_action_logs WHERE ticket_id IN {tic_in}', tic_params, "ticket_action_logs", deleted)

    # 3. Direct user-FK rows in every referencing table.
    for table, column in refs:
        if table == "users":
            # Self-FK (manager_id, supervisor_id, etc.) — null it out so the parent
            # delete below isn't blocked.
            _run(
                f'UPDATE users SET "{column}" = NULL WHERE "{column}" IN {in_clause}',
                base_params, f"users.{column} (nulled)", deleted,
            )
            continue
        _run(
            f'DELETE FROM "{table}" WHERE "{column}" IN {in_clause}',
            base_params, f"{table}.{column}", deleted,
        )

    # 4. Finally the users themselves, one at a time so a single FK miss doesn't
    #    block the rest.
    for uid in extra_ids:
        _run(
            "DELETE FROM users WHERE id = :uid",
            {"uid": uid}, "users", deleted,
        )

    return deleted


def main() -> None:
    Base.metadata.create_all(bind=engine)
    print(f"Target database: {engine.url}")

    # Identify users to remove FIRST. Anyone not in the keep email set is fair game.
    # If the keep-list users already exist, they are preserved verbatim. The seed
    # step at the end is idempotent (updates name/role/password) and won't duplicate.
    db = SessionLocal()
    try:
        extras = (
            db.query(User.id, User.email)
            .filter(~User.email.in_(KEEP_EMAILS))
            .all()
        )
        extra_ids = [str(uid) for uid, _ in extras]
        existing_keep = db.query(User).filter(User.email.in_(KEEP_EMAILS)).count()
        print(f"Keep set (will be ensured by seed): {', '.join(sorted(KEEP_EMAILS))}")
        print(f"Currently in DB matching keep set: {existing_keep}")
        print(f"Users to remove: {len(extra_ids)}")
        for uid, email in extras:
            print(f"  - {email}")
    finally:
        db.close()

    if extra_ids:
        deleted = _delete_cascade_for_users(extra_ids)
        nonzero = {k: v for k, v in deleted.items() if v}
        print(f"\nDeleted rows:")
        for table, count in sorted(nonzero.items()):
            print(f"  {count:>6} {table}")
    else:
        print("Nothing to delete.")

    # Now (re-)seed the two canonical users. Idempotent: creates if missing, updates if present.
    print("\nSeeding canonical users...")
    seed_two_users()
    print(f"\nDone. {len(KEEP_EMAILS)} user(s) should now be in DB.")


if __name__ == "__main__":
    main()

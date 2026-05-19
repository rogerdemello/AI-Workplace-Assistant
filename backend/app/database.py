from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import QueuePool, StaticPool
from .config import settings

DATABASE_URL = settings.DATABASE_URL

# SQLite compatibility: models use PostgreSQL UUID/JSONB types; patch the SQLite
# dialect to render them as CHAR(36)/JSON so dev-mode boots without migrations.
if DATABASE_URL.startswith("sqlite"):
    from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler

    SQLiteTypeCompiler.visit_UUID = lambda self, type_, **kw: "CHAR(36)"
    SQLiteTypeCompiler.visit_JSONB = lambda self, type_, **kw: "JSON"

    from sqlalchemy.dialects.postgresql import UUID as PGUUID
    from sqlalchemy import UUID as SQLUUID
    from sqlalchemy.ext.compiler import compiles

    @compiles(PGUUID, "sqlite")
    def _compile_pg_uuid_for_sqlite(_type, _compiler, **_kwargs):
        return "CHAR(36)"

    @compiles(SQLUUID, "sqlite")
    def _compile_sql_uuid_for_sqlite(_type, _compiler, **_kwargs):
        return "CHAR(36)"


def _build_connect_args(database_url: str) -> dict:
    """Build engine connect args with safe defaults for managed Postgres providers."""
    try:
        parsed_url = make_url(database_url)
    except Exception:
        return {}

    host = (parsed_url.host or "").lower()
    query_params = parsed_url.query or {}

    # Supabase connections should be TLS-enabled; enforce sslmode only when omitted.
    if host.endswith(".supabase.co") and "sslmode" not in query_params:
        return {"sslmode": "require"}

    return {}

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )
else:
    connect_args = _build_connect_args(DATABASE_URL)

    # Supabase free tier has ~15 non-superuser connection slots total. With
    # uvicorn --reload + APScheduler we burn through them fast. Cap the pool
    # tight for managed providers; a dedicated Postgres can override via env
    # vars if needed.
    try:
        parsed = make_url(DATABASE_URL)
        host = (parsed.host or "").lower()
    except Exception:
        host = ""

    is_managed_low_tier = host.endswith(".supabase.co") or "pooler.supabase.com" in host

    if is_managed_low_tier:
        pool_size = 2
        max_overflow = 3
    else:
        pool_size = 10
        max_overflow = 20

    engine = create_engine(
        DATABASE_URL,
        poolclass=QueuePool,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,
        pool_recycle=300,  # recycle idle connections after 5 min (Supabase kills idle conns)
        pool_timeout=10,   # don't wait forever for a slot
        connect_args=connect_args,
        echo=False,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

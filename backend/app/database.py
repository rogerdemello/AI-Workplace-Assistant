from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import QueuePool, StaticPool
from .config import settings

DATABASE_URL = settings.DATABASE_URL


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
    engine = create_engine(
        DATABASE_URL,
        poolclass=QueuePool,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600,
        connect_args=connect_args,
        echo=False
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

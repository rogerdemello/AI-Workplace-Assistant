import pytest
import uuid
import os
import sys
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import String, UUID as SQLUUID
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
import uuid as uuid_module

SQLiteTypeCompiler.visit_UUID = lambda self, type_, **kw: "CHAR(36)"
SQLiteTypeCompiler.visit_JSONB = lambda self, type_, **kw: "JSON"

os.environ["AZURE_OPENAI_API_KEY"] = "test-api-key"
os.environ["AZURE_OPENAI_ENDPOINT"] = "https://test.openai.azure.com/"
os.environ["AZURE_OPENAI_DEPLOYMENT"] = "gpt-4"
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["ALGORITHM"] = "HS256"
os.environ["REDIS_URL"] = "redis://localhost:6379"
os.environ["TESTING"] = "1"
os.environ["FAST_CHAT_MODE"] = "true"
os.environ["CHAT_SKIP_INTELLIGENCE_SNAPSHOT"] = "false"


class GUID(TypeDecorator):
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PGUUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid_module.UUID):
            return str(value)
        return str(uuid_module.UUID(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid_module.UUID):
            return value
        return uuid_module.UUID(value)


@compiles(PGUUID, "sqlite")
def _compile_uuid_for_sqlite(_type, _compiler, **_kwargs):
    """Allow models using PostgreSQL UUID columns to be created in SQLite tests."""
    return "CHAR(36)"


@compiles(SQLUUID, "sqlite")
def _compile_sql_uuid_for_sqlite(_type, _compiler, **_kwargs):
    return "CHAR(36)"


@pytest.fixture(scope="function", autouse=True)
def setup_test_db():
    """Use the same SQLAlchemy engine as the app so metadata and sessions stay aligned."""
    from app.database import Base, engine
    import app.models  # noqa: F401 — register all models on Base.metadata
    try:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        yield
        Base.metadata.drop_all(bind=engine)
    except Exception:
        pytest.skip("Database tables creation failed")


@pytest.fixture(scope="function", autouse=True)
def reset_rate_limiter_state():
    from app.middleware.rate_limit import get_rate_limiter

    limiter = get_rate_limiter()
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture(scope="function")
def db():
    from app.database import SessionLocal

    db_session = SessionLocal()
    try:
        yield db_session
    finally:
        db_session.close()


@pytest.fixture(scope="function")
def client(db):
    from app.database import get_db
    from app.main import app
    
    def override_get_db():
        try:
            yield db
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as c:
        yield c
    
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db):
    from app.models.user import User, UserRole, UserStatus
    from app.auth import hash_password
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        name="Test User",
        hashed_password=hash_password("testpass123"),
        role=UserRole.employee,
        status=UserStatus.active
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def hr_user(db):
    from app.models.user import User, UserRole, UserStatus
    from app.auth import hash_password
    user = User(
        id=uuid.uuid4(),
        email="hr@example.com",
        name="HR User",
        hashed_password=hash_password("hrpass123"),
        role=UserRole.hr,
        status=UserStatus.active
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def manager_user(db):
    from app.models.user import User, UserRole, UserStatus
    from app.auth import hash_password
    user = User(
        id=uuid.uuid4(),
        email="manager@example.com",
        name="Manager User",
        hashed_password=hash_password("managerpass123"),
        role=UserRole.manager,
        status=UserStatus.active
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def admin_user(db):
    from app.models.user import User, UserRole, UserStatus
    from app.auth import hash_password
    user = User(
        id=uuid.uuid4(),
        email="admin@example.com",
        name="Admin User",
        hashed_password=hash_password("adminpass123"),
        role=UserRole.admin,
        status=UserStatus.active
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user):
    from app.auth import create_access_token
    token = create_access_token(data={"sub": str(test_user.id), "role": test_user.role.value})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def hr_auth_headers(hr_user):
    from app.auth import create_access_token
    token = create_access_token(data={"sub": str(hr_user.id), "role": hr_user.role.value})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def manager_auth_headers(manager_user):
    from app.auth import create_access_token
    token = create_access_token(data={"sub": str(manager_user.id), "role": manager_user.role.value})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_auth_headers(admin_user):
    from app.auth import create_access_token
    token = create_access_token(data={"sub": str(admin_user.id), "role": admin_user.role.value})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_ai_client(monkeypatch):
    mock_client = MagicMock()
    mock_client.chat.completions.create = lambda **kwargs: {"choices": [{"message": {"content": "Mock AI response"}}], "usage": {"total_tokens": 15}}
    mock_client.embeddings.create = lambda **kwargs: {"data": [{"embedding": [0.1] * 1536, "index": 0}]}
    
    monkeypatch.setattr("app.ai_client.client.client", mock_client)
    return mock_client


@pytest.fixture
def mock_redis(monkeypatch):
    mock_redis = MagicMock()
    mock_redis.ping.return_value = True
    mock_redis.get.return_value = None
    mock_redis.setex.return_value = True
    mock_redis.delete.return_value = True
    
    def mock_get_redis():
        return mock_redis
    
    monkeypatch.setattr("app.services.chat.get_redis_client", mock_get_redis)
    return mock_redis

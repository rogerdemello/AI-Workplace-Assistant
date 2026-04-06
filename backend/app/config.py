from pydantic_settings import BaseSettings
from typing import Optional
import os
from pathlib import Path

# Determine project root (parent of backend/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:your-password@db.your-project.supabase.co:5432/postgres?sslmode=require"
    REDIS_URL: str = "redis://localhost:6379"
    AZURE_OPENAI_API_KEY: str = "mock-key"
    AZURE_OPENAI_ENDPOINT: str = "https://mock.openai.azure.com"
    AZURE_OPENAI_DEPLOYMENT: str = "gpt-4"
    AZURE_OPENAI_API_VERSION: str = "2024-12-01-preview"
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    MICROSOFT_CLIENT_ID: str = ""
    MICROSOFT_CLIENT_SECRET: str = ""
    VITE_API_URL: str = "http://localhost:8000"

    SUPABASE_URL: Optional[str] = None
    SUPABASE_SERVICE_KEY: Optional[str] = None
    SUPABASE_KEY: Optional[str] = None
    SUPABASE_JWT_SECRET: Optional[str] = None
    ALLOW_HEADER_ROLE_AUTH: bool = False

    class Config:
        env_file = PROJECT_ROOT / ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()

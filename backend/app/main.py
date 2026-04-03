from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import time
import os
from contextlib import asynccontextmanager

from .config import settings
from .database import engine, Base
from .api.v1.auth import router as auth_router
from .api.v1.demo_auth import router as demo_auth_router
from .api.v1.chat import router as chat_router
from .api.v1.ai import router as ai_router
from .api.v1.rag import router as rag_router
from .api.v1.tickets import router as tickets_router
from .api.v1.email import router as email_router
from .api.v1.sentiment import router as sentiment_router
from .api.v1.surveys import router as surveys_router
from .api.v1.feedback import router as feedback_router
from .api.v1.integrations import router as integrations_router
from .api.v1.rooms import router as rooms_router
from .api.v1.analytics import router as analytics_router
from .middleware.rate_limit import rate_limit_middleware
from .middleware.budget import budget_middleware
from .middleware.security import (
    security_headers_middleware,
    sql_injection_protection_middleware,
    xss_protection_middleware,
    mask_pii
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up HR Assistant API...")
    
    if not settings.DATABASE_URL.startswith("sqlite"):
        logger.info(f"Connecting to PostgreSQL: {settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else 'database'}")
    else:
        logger.info("Using SQLite for development")
    
    if not settings.DATABASE_URL.startswith("sqlite"):
        Base.metadata.create_all(bind=engine)
    
    yield
    
    # Shutdown
    logger.info("Shutting down HR Assistant API...")


app = FastAPI(
    title="HR Assistant API",
    description="AI-powered HR Workplace Assistant",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Configuration - Allow frontend origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security middleware
app.middleware("http")(security_headers_middleware)
app.middleware("http")(sql_injection_protection_middleware)
app.middleware("http")(xss_protection_middleware)

# Rate limiting middleware (applied via decorator)
app.middleware("http")(rate_limit_middleware)

# Budget tracking middleware (for AI endpoints)
app.middleware("http")(budget_middleware)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware to log all incoming requests and response times."""
    start_time = time.time()
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    
    # Log with masked PII
    log_message = f"{request.method} {request.url.path} - Status: {response.status_code} - Duration: {process_time:.3f}s"
    logger.info(mask_pii(log_message))
    
    response.headers["X-Process-Time"] = str(process_time)
    return response


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "ok",
        "version": "1.0.0"
    }


# Include API routers with versioned routes
app.include_router(auth_router, prefix="/api/v1")
app.include_router(demo_auth_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(ai_router, prefix="/api/v1")
app.include_router(rag_router, prefix="/api/v1")
app.include_router(tickets_router, prefix="/api/v1")
app.include_router(email_router, prefix="/api/v1")
app.include_router(sentiment_router, prefix="/api/v1")
app.include_router(surveys_router, prefix="/api/v1")
app.include_router(feedback_router, prefix="/api/v1")
app.include_router(integrations_router, prefix="/api/v1")
app.include_router(rooms_router, prefix="/api/v1")
app.include_router(analytics_router, prefix="/api/v1")


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint returning API information."""
    return {
        "message": "HR Assistant API",
        "version": "1.0.0",
        "docs": "/docs"
    }

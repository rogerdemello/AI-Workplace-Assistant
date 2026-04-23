from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import logging
import time
import os
from contextlib import asynccontextmanager
import asyncio
from typing import Optional

from .config import settings
from .core.feature_flags import get_feature_flags
from .database import engine, Base, SessionLocal
from .models import hr_alert as _hr_alert_model  # noqa: F401 — register HrAlert with Base.metadata
from .models import leave_request as _leave_request_model  # noqa: F401 — register LeaveRequest with Base.metadata
from .models import personal_fact as _personal_fact_model  # noqa: F401 — register PersonalFact with Base.metadata
from .models import onboarding_buddy as _onboarding_buddy_model  # noqa: F401 — register OnboardingBuddy with Base.metadata
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
from .api.v1.wellbeing import router as wellbeing_router
from .api.v1.wellness import router as wellness_router
from .api.v1.hr_alerts import router as hr_alerts_router
from .api.v1.leave import router as leave_router
from .api.v1.attachments import router as attachments_router
from .api.v1.mood import router as mood_router
from .api.v1.appreciation import router as appreciation_router
from .api.v1.onboarding import router as onboarding_router
from .api.v1.buddies import router as buddies_router
from .routes import hr_auth as hr_auth_routes
from .routes import hr_dashboard as hr_dashboard_routes
from .routes import hr_tickets as hr_tickets_routes
from .routes import hr_employees as hr_employees_routes
from .routes import hr_insights as hr_insights_routes
from .routes import hr_actions as hr_actions_routes
from .services.scheduler import start_scheduler, stop_scheduler
from .services.analytics import register_event_driven_analytics
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


async def _alert_background_loop() -> None:
    """Periodic proactive wellbeing scan → `hr_alerts` (default: daily)."""
    if os.getenv("ENABLE_ALERT_BACKGROUND", "true").lower() not in ("1", "true", "yes"):
        return
    interval = int(os.getenv("ALERT_SCAN_INTERVAL_SECONDS", "86400"))
    await asyncio.sleep(20)
    from .api.v1.hr_alerts import _store_from_wellbeing

    while True:
        db = SessionLocal()
        try:
            _store_from_wellbeing(db)
        except Exception:
            logger.exception("Background alert scan failed")
            db.rollback()
        finally:
            db.close()
        await asyncio.sleep(max(60, interval))


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up HR Assistant API...")
    is_testing = os.getenv("TESTING", "0").lower() in ("1", "true", "yes")
    flags = get_feature_flags()
    
    if not settings.DATABASE_URL.startswith("sqlite"):
        logger.info(f"Connecting to PostgreSQL: {settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else 'database'}")
    else:
        logger.info("Using SQLite for development")
    
    if not settings.DATABASE_URL.startswith("sqlite"):
        Base.metadata.create_all(bind=engine)

    if flags.enable_analytics_events:
        register_event_driven_analytics()
    
    alert_task: Optional[asyncio.Task] = None
    if (not is_testing) and os.getenv("ENABLE_ALERT_BACKGROUND", "true").lower() in ("1", "true", "yes"):
        alert_task = asyncio.create_task(_alert_background_loop())

    scheduler_started = False
    if not is_testing:
        start_scheduler()
        scheduler_started = True

    yield

    if alert_task:
        alert_task.cancel()
        try:
            await alert_task
        except asyncio.CancelledError:
            pass
    if scheduler_started:
        stop_scheduler()
    # Shutdown
    logger.info("Shutting down HR Assistant API...")


app = FastAPI(
    title="HR Assistant API",
    description="AI-powered HR Workplace Assistant",
    version="1.0.0",
    lifespan=lifespan
)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for error in exc.errors():
        field = ".".join(str(x) for x in error.get("loc", []))
        message = error.get("msg", "")
        errors.append({"field": field, "message": message})
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Validation failed",
            "errors": errors,
        },
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
app.include_router(wellbeing_router, prefix="/api/v1")
app.include_router(wellness_router, prefix="/api/v1")
app.include_router(hr_alerts_router, prefix="/api/v1")
app.include_router(leave_router, prefix="/api/v1")
app.include_router(attachments_router, prefix="/api/v1")
app.include_router(mood_router, prefix="/api/v1")
app.include_router(appreciation_router, prefix="/api/v1")
app.include_router(onboarding_router, prefix="/api/v1")
app.include_router(buddies_router, prefix="/api/v1")
app.include_router(hr_auth_routes.router, prefix="/hr")
app.include_router(hr_auth_routes.legacy_router, prefix="/api/v1")
app.include_router(hr_dashboard_routes.router, prefix="/hr")
app.include_router(hr_tickets_routes.router, prefix="/hr")
app.include_router(hr_employees_routes.router, prefix="/hr")
app.include_router(hr_employees_routes.legacy_router, prefix="/api/v1")
app.include_router(hr_insights_routes.router, prefix="/hr")
app.include_router(hr_actions_routes.router, prefix="/hr")


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint returning API information."""
    return {
        "message": "HR Assistant API",
        "version": "1.0.0",
        "docs": "/docs"
    }

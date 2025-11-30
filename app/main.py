"""Main FastAPI application for Greek Alphabet Mastery."""
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.routers import user, quiz
from app.db.init_db import init_db
from app.db.database import get_db
from app.logging_config import setup_logging, get_logger
from app.config import settings

# Set up logging on module import
log_level = settings.LOG_LEVEL if settings.LOG_LEVEL else None
setup_logging(log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database and logging on startup.

    This function runs once when the application starts, performing:
    - Database table creation
    - Schema migrations
    - Initial data seeding
    """
    logger.info("Application startup initiated")
    try:
        init_db()
        logger.info("Database initialization completed successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}", exc_info=True)
        raise

    yield

    logger.info("Application shutdown complete")


app = FastAPI(
    title="Greek Alphabet Mastery API",
    description="""
    Mobile-first adaptive quiz application for mastering the Greek alphabet.

    ## Features

    - **Adaptive Learning**: Questions dynamically adjust based on user performance
    - **Spaced Repetition**: Focus on letters that need more practice
    - **Multiple Question Types**: Letter recognition, audio pronunciation, name-to-symbol
    - **Progress Tracking**: Detailed statistics and mastery scores per letter
    - **Anonymous Sessions**: No account required, uses browser cookies

    ## Quiz Flow

    1. **Start Quiz**: POST to `/api/quiz/start` to get 14 questions
    2. **Submit Answers**: POST each answer to `/api/quiz/{quiz_id}/answer`
    3. **View Summary**: Receive performance summary with last question
    4. **Resume Quiz**: GET `/api/quiz/{quiz_id}/state` to restore in-progress quiz

    ## Learning Algorithm

    - First 10 quizzes use **balanced mode** (even distribution across all letters)
    - After 10 quizzes, **adaptive mode** activates (60% weak letters, 40% coverage)
    - Mastery score considers accuracy, consistency, and recent streak
    - Letters are mastered after 8+ attempts with 90%+ accuracy and 3+ streak
    """,
    version="1.4.2",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_tags=[
        {
            "name": "user",
            "description": "User session management and statistics"
        },
        {
            "name": "quiz",
            "description": "Quiz creation, answer submission, and progress tracking"
        },
        {
            "name": "health",
            "description": "Service health and readiness checks"
        }
    ]
)

# Add rate limiting middleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

logger.info(f"Rate limiting enabled: default 100 requests/minute per IP")

# Add CSRF protection for production
if settings.is_production:
    from starlette.middleware.sessions import SessionMiddleware
    app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)
    logger.info("Session middleware enabled for CSRF protection")

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Set up templates
templates = Jinja2Templates(directory="app/templates")

# Include routers
app.include_router(user.router)
app.include_router(quiz.router)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve the main application page."""
    logger.debug("Serving home page")
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/quiz", response_class=HTMLResponse)
async def quiz_page(request: Request):
    """Serve the quiz page."""
    logger.debug("Serving quiz page")
    return templates.TemplateResponse("quiz.html", {"request": request})


@app.get("/summary", response_class=HTMLResponse)
async def summary_page(request: Request):
    """Serve the quiz summary page."""
    logger.debug("Serving summary page")
    return templates.TemplateResponse("summary.html", {"request": request})


@app.get("/health", tags=["health"])
async def health_check(db: Session = Depends(get_db)):
    """Enhanced health check endpoint with database verification.

    This endpoint verifies:
    - API server is responding
    - Database connection is working
    - Basic query execution succeeds

    Returns:
        200 OK: Service is healthy and database is accessible
        503 Service Unavailable: Database connection failed

    Example Response (Healthy):
        {
            "status": "healthy",
            "database": "connected",
            "timestamp": "2025-11-29T10:30:00.000000Z",
            "environment": "production"
        }

    Example Response (Unhealthy):
        {
            "status": "unhealthy",
            "database": "disconnected",
            "error": "connection refused",
            "timestamp": "2025-11-29T10:30:00.000000Z"
        }
    """
    timestamp = datetime.utcnow().isoformat() + "Z"

    try:
        # Attempt a simple database query
        db.execute(text("SELECT 1"))
        logger.debug("Health check passed")

        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": timestamp,
            "environment": settings.ENVIRONMENT
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)

        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "error": str(e),
                "timestamp": timestamp
            }
        )


@app.get("/readiness", tags=["health"])
async def readiness_check(db: Session = Depends(get_db)):
    """Readiness check for Kubernetes/container orchestration.

    Similar to health check but specifically designed for orchestration
    platforms to determine if the service is ready to accept traffic.

    Returns:
        200 OK: Service is ready
        503 Service Unavailable: Service is not ready
    """
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready", "timestamp": datetime.utcnow().isoformat() + "Z"}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "not ready", "error": str(e)}
        )

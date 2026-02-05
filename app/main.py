"""
Pineapple FX - Foreign Exchange Rate Service

A FastAPI application providing EUR to USD exchange rate summaries
with day-by-day breakdowns and aggregate statistics.

Coins alone do not tell the story; this shows you the pattern and the change.
"""

import logging
import secrets
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.models import (
    BreakdownType,
    ErrorResponse,
    HealthResponse,
    SummaryResponse,
)
from app.services.fx_service import FXServiceError, get_fx_summary, clear_cache
from app.settings import (
    DEBUG,
    RATE_LIMIT_HEALTH,
    RATE_LIMIT_SUMMARY,
    RATE_LIMIT_ADMIN,
    get_admin_key,
)

# Logging configuration
logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Admin API key (generated once at startup if not configured)
ADMIN_API_KEY = get_admin_key()

# Rate limiter: keyed by client IP address
limiter = Limiter(key_func=get_remote_address)


def verify_admin_key(x_admin_key: str) -> None:
    """Verify the admin API key. Raises 401 if invalid."""
    if not secrets.compare_digest(x_admin_key, ADMIN_API_KEY):
        raise HTTPException(
            status_code=401,
            detail="Invalid admin API key",
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown handler."""
    logger.info("Pineapple FX starting up...")
    if not get_admin_key():
        logger.warning(f"No PINEAPPLE_ADMIN_KEY set. Generated temporary key: {ADMIN_API_KEY}")
    yield
    logger.info("Pineapple FX shutting down...")


# FastAPI application
app = FastAPI(
    title="Pineapple FX",
    description="""
Foreign Exchange Rate Service

Get EUR to USD exchange rate summaries with daily breakdowns and statistics.

**Features:**
- Day-by-day rate breakdown with percentage changes
- Aggregate statistics (start/end rates, total change, mean)
- Automatic fallback to local data when API is unavailable
- Built-in caching for performance
- Retry logic for reliability
- Rate limiting for API protection
    """,
    version="1.0.0",
    lifespan=lifespan,
    responses={
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)

# Attach rate limiter to app state
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Return a friendly message when rate limit is exceeded."""
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Rate limit exceeded. Please slow down.",
            "error_code": "RATE_LIMIT_EXCEEDED"
        }
    )


# CORS middleware - allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (frontend UI)
static_path = Path(__file__).parent.parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root():
    """Serve the frontend UI."""
    index_path = static_path / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text())
    return HTMLResponse(
        content="""
        <html>
            <head><title>Pineapple FX</title></head>
            <body>
                <h1>Pineapple FX</h1>
                <p>Welcome! Visit <a href="/docs">/docs</a> for API documentation.</p>
            </body>
        </html>
        """
    )


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Health check endpoint",
    description=f"Returns service health status and version. Rate limited to {RATE_LIMIT_HEALTH}.",
)
@limiter.limit(RATE_LIMIT_HEALTH)
async def health_check(request: Request) -> HealthResponse:
    """Health check endpoint. Returns service status and version."""
    return HealthResponse(
        status="healthy",
        service="Pineapple FX",
        version="1.0.0",
    )


@app.get(
    "/summary",
    response_model=SummaryResponse,
    tags=["FX Rates"],
    summary="Get FX rate summary",
    description=f"Get EUR to USD exchange rate summary for a date range. Rate limited to {RATE_LIMIT_SUMMARY}.",
    responses={
        200: {"description": "Successful response with FX rate data"},
        400: {"model": ErrorResponse, "description": "Invalid request parameters"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        500: {"model": ErrorResponse, "description": "Service error"},
    },
)
@limiter.limit(RATE_LIMIT_SUMMARY)
async def get_summary(
    request: Request,
    start_date: date = Query(
        ...,
        description="Start date (inclusive) in YYYY-MM-DD format",
        examples=["2025-01-15"],
    ),
    end_date: date = Query(
        ...,
        description="End date (inclusive) in YYYY-MM-DD format",
        examples=["2025-01-31"],
    ),
    breakdown: BreakdownType = Query(
        default=BreakdownType.DAY,
        description="Breakdown granularity: 'day' for daily rates, 'none' for totals only",
    ),
) -> SummaryResponse:
    """
    Get FX rate summary for EUR to USD.
    
    Returns exchange rate data with optional day-by-day breakdown including:
    - Daily rates and percentage changes from prior day
    - Aggregate statistics: start/end rates, total percentage change, mean rate
    
    Data is fetched from the Frankfurter API with automatic fallback to local data.
    """
    if end_date < start_date:
        raise HTTPException(
            status_code=400,
            detail="end_date must be on or after start_date",
        )
    
    try:
        return await get_fx_summary(start_date, end_date, breakdown)
    except FXServiceError as e:
        logger.error(f"FX service error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error in get_summary")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred. Please try again later.",
        )


@app.post(
    "/cache/clear",
    tags=["Admin"],
    summary="Clear FX rate cache",
    description=f"Clears the in-memory FX rate cache. Requires admin API key. Rate limited to {RATE_LIMIT_ADMIN}.",
    responses={
        200: {"description": "Cache cleared successfully"},
        401: {"model": ErrorResponse, "description": "Invalid or missing admin API key"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    },
)
@limiter.limit(RATE_LIMIT_ADMIN)
async def clear_fx_cache(
    request: Request,
    x_admin_key: str = Header(..., description="Admin API key"),
):
    """
    Clear the FX rate cache.
    
    Requires the X-Admin-Key header with a valid admin API key.
    Set the PINEAPPLE_ADMIN_KEY environment variable to configure the key.
    """
    verify_admin_key(x_admin_key)
    count = clear_cache()
    return {"message": f"Cache cleared. {count} entries removed."}

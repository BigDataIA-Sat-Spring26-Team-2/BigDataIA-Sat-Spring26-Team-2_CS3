# app/main.py


from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.routers import assessments, companies, dimension_scores, industries, health, documents, signal
from app.errors import (
    http_exception_handler,
    validation_exception_handler,
    unhandled_exception_handler,
    snowflake_exception_handler,
)

# Optional Snowflake error mapping
try:
    from snowflake.connector.errors import ProgrammingError, DatabaseError
except Exception:
    ProgrammingError = None
    DatabaseError = None


# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="PE Org-AI-R Platform Team-2",
    description="AI Readiness Platform",
)

# Add rate limiter to app state
app.state.limiter = limiter


# Custom rate limit error handler
@app.exception_handler(RateLimitExceeded)
async def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded",
            "message": "You have made too many requests. Please try again later.",
            "detail": str(exc.detail)
        }
    )


# Exception handlers
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

if ProgrammingError:
    app.add_exception_handler(ProgrammingError, snowflake_exception_handler)
if DatabaseError:
    app.add_exception_handler(DatabaseError, snowflake_exception_handler)


# Routers
app.include_router(health.router, prefix="/api/v1")
app.include_router(assessments.router, prefix="/api/v1")
app.include_router(companies.router, prefix="/api/v1")
app.include_router(dimension_scores.router, prefix="/api/v1")
app.include_router(industries.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(signal.router, prefix="/api/v1/signals", tags=["Signals"])


@app.get("/")
def root():
    return {"message": "PE Org-AI-R Platform is running"}


@app.get("/health")
def health_check():
    return {"status": "ok"}

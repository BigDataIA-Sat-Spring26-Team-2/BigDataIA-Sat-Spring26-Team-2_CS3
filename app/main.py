# app/main.py
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError

from app.routers import assessments, companies, dimension_scores, industries, health
from app.errors import (
    http_exception_handler,
    validation_exception_handler,
    unhandled_exception_handler,
    snowflake_exception_handler,
)

# Snowflake exceptions (optional mapping)
try:
    from snowflake.connector.errors import ProgrammingError, DatabaseError
except Exception:
    ProgrammingError = None
    DatabaseError = None


app = FastAPI(
    title="PE Org-AI-R Platform Team-2",
    description="AI Readiness Platform"
)


app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)


if ProgrammingError:
    app.add_exception_handler(ProgrammingError, snowflake_exception_handler)
if DatabaseError:
    app.add_exception_handler(DatabaseError, snowflake_exception_handler)

# ✅ Routers
app.include_router(health.router, prefix="/api/v1")
app.include_router(dimension_scores.router, prefix="/api/v1")

app.include_router(assessments.router, prefix="/api/v1")
app.include_router(companies.router, prefix="/api/v1")
app.include_router(industries.router, prefix="/api/v1")


@app.get("/")
def root():
    return {"message": "PE Org-AI-R Platform is running"}


@app.get("/health")
def health_check():
    return {"status": "ok"}

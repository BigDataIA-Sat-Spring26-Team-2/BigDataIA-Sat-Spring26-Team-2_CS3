# app/services/__init__.py

# This file can be empty or contain imports for convenience
# If you want to import services like: from app.services import company_service

from app.services import (
    assessments_service,
    company_service,
    dimension_scores_service,
    industry_service,
    redis_cache,
    s3_storage,
    sec_edgar_service,
    signal_service,
    snowflake,
)

# Create alias for backward compatibility
signals_service = signal_service

__all__ = [
    "assessments_service",
    "company_service",
    "dimension_scores_service",
    "industry_service",
    "redis_cache",
    "s3_storage",
    "sec_edgar_service",
    "signal_service",
    "snowflake",
]
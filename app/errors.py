# app/errors.py
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY, HTTP_500_INTERNAL_SERVER_ERROR
import traceback
import structlog

from app.models.errors import ErrorResponse

logger = structlog.get_logger()


def http_exception_handler(request: Request, exc: HTTPException):
    payload = ErrorResponse(
        error="http_error",
        message=str(exc.detail),
        details={"path": str(request.url.path)},
    )
    return JSONResponse(status_code=exc.status_code, content=jsonable_encoder(payload))


def validation_exception_handler(request: Request, exc: RequestValidationError):
    payload = ErrorResponse(
        error="validation_error",
        message="Request validation failed",
        details=exc.errors(),
    )
    return JSONResponse(
        status_code=HTTP_422_UNPROCESSABLE_ENTITY,
        content=jsonable_encoder(payload),
    )


def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Handle unexpected errors.
    NOW SHOWS ACTUAL ERROR MESSAGE instead of hiding it!
    """
    # Log full traceback for debugging
    error_traceback = traceback.format_exc()
    logger.error(
        "unhandled_exception",
        path=str(request.url.path),
        error_message=str(exc),
        error_type=type(exc).__name__,
        traceback=error_traceback
    )
    
    # Print to console for immediate visibility
    print("\n" + "="*70)
    print("UNHANDLED EXCEPTION:")
    print("="*70)
    print(error_traceback)
    print("="*70 + "\n")
    
    # Return detailed error (helpful for debugging)
    payload = ErrorResponse(
        error="http_error",
        message=f"V^R calculation failed: {type(exc).__name__}: {str(exc)}",
        details={"path": str(request.url.path), "error_type": type(exc).__name__},
    )
    return JSONResponse(
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        content=jsonable_encoder(payload),
    )


# Optional: If you want Snowflake errors to have a nicer message
def snowflake_exception_handler(request: Request, exc: Exception):
    msg = str(exc)
    
    logger.error("snowflake_error", error=msg, path=str(request.url.path))
    
    payload = ErrorResponse(
        error="snowflake_error",
        message="Snowflake query failed",
        details={"reason": msg, "path": str(request.url.path)},
    )
    return JSONResponse(status_code=500, content=jsonable_encoder(payload))
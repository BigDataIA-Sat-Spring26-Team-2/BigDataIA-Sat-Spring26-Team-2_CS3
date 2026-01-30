# app/errors.py
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY, HTTP_500_INTERNAL_SERVER_ERROR

from app.models.errors import ErrorResponse


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
   
    payload = ErrorResponse(
        error="internal_server_error",
        message="An unexpected error occurred",
        details={"path": str(request.url.path)},
    )
    return JSONResponse(
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        content=jsonable_encoder(payload),
    )


# Optional: If you want Snowflake errors to have a nicer message
def snowflake_exception_handler(request: Request, exc: Exception):
    msg = str(exc)
    payload = ErrorResponse(
        error="snowflake_error",
        message="Snowflake query failed",
        details={"reason": msg, "path": str(request.url.path)},
    )
    return JSONResponse(status_code=500, content=jsonable_encoder(payload))

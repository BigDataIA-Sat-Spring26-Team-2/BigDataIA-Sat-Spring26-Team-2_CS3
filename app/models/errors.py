# app/models/errors.py
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    error: str
    message: str
    details: Optional[Any] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

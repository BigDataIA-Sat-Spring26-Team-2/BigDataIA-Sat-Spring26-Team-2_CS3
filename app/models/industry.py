# app/models/industry.py
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import Sector


class IndustryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    sector: Sector
    h_r_base: float = Field(..., ge=0, le=100)


class IndustryCreate(IndustryBase):
    pass


class IndustryResponse(IndustryBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True

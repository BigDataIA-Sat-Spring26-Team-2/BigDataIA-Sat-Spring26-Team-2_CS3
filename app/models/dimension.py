from pydantic import BaseModel, Field, field_validator
from uuid import UUID, uuid4
from datetime import datetime

from app.models.enums import Dimension


class DimensionScore(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    assessment_id: UUID  #Many dimension scores → one assessment (1-to-many)
    dimension: Dimension #Enum for dimension type
    score: int = Field(..., ge=0, le=100)
    weight: float = Field(..., ge=0.0, le=1.0)  #All weights together will later sum to 1.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime | None = None

    @field_validator("weight")
    @classmethod
    def validate_weight(cls, v):
        if v > 1.0:
            raise ValueError("Weight must be between 0 and 1")
        return v

    class Config:
        from_attributes = True

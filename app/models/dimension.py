from pydantic import BaseModel, Field, field_validator, model_validator
from uuid import UUID, uuid4
from datetime import datetime
from typing import Dict, Optional

from app.models.enums import Dimension


DIMENSION_WEIGHTS = {
    Dimension.DATA_INFRASTRUCTURE: 0.25,
    Dimension.AI_GOVERNANCE: 0.20,
    Dimension.TECHNOLOGY_STACK: 0.15,
    Dimension.TALENT_SKILLS: 0.15,
    Dimension.LEADERSHIP_VISION: 0.10,
    Dimension.USE_CASE_PORTFOLIO: 0.10,
    Dimension.CULTURE_CHANGE: 0.05,
}

class DimensionScoreBase(BaseModel):
    assessment_id: UUID
    dimension: Dimension
    score: float = Field(..., ge=0, le=100)
    weight: Optional[float] = Field(default=None, ge=0, le=1)
    confidence: float = Field(default=0.8, ge=0, le=1)
    evidence_count: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def set_default_weight(self) -> "DimensionScoreBase":
        if self.weight is None:
            self.weight = DIMENSION_WEIGHTS.get(self.dimension, 0.1)
        return self

class DimensionScoreCreate(DimensionScoreBase):
    pass

class DimensionScoreResponse(DimensionScoreBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True
class DimensionWeightsResponse(BaseModel):
    weights: Dict[str, float]

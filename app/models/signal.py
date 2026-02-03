from pydantic import BaseModel, Field, model_validator
from uuid import UUID, uuid4
from datetime import datetime, timezone
from typing import Optional, Dict
from typing import List


from app.models.enums import SignalCategory, SignalSource


class ExternalSignal(BaseModel):
    """A single external signal observation."""
    id: UUID = Field(default_factory=uuid4)
    company_id: Optional[UUID] = None
    category: SignalCategory
    source: SignalSource
    signal_date: datetime
    raw_value: str  # Original observation (e.g., "18/25 AI jobs")
    normalized_score: float = Field(ge=0, le=100)
    confidence: float = Field(default=0.8, ge=0, le=1)
    metadata: Dict = Field(default_factory=dict)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    class Config:
        from_attributes = True


class CompanySignalSummary(BaseModel):
    """Aggregated signals for a company."""
    company_id: UUID
    ticker: str
    technology_hiring_score: float = Field(ge=0, le=100, default=0.0)
    innovation_activity_score: float = Field(ge=0, le=100, default=0.0)
    digital_presence_score: float = Field(ge=0, le=100, default=0.0)
    leadership_signals_score: float = Field(ge=0, le=100, default=0.0)
    composite_score: float = Field(ge=0, le=100, default=0.0)
    signal_count: int = 0
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @model_validator(mode='after')
    def calculate_composite(self) -> 'CompanySignalSummary':
        """Calculate weighted composite score."""
        self.composite_score = (
            0.30 * self.technology_hiring_score +
            0.25 * self.innovation_activity_score +
            0.25 * self.digital_presence_score +
            0.20 * self.leadership_signals_score
        )
        return self

    class Config:
        from_attributes = True


class SignalCreate(BaseModel):
    """Create a new signal (without id)."""
    company_id: UUID
    category: SignalCategory
    source: SignalSource
    signal_date: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    raw_value: str
    normalized_score: float = Field(ge=0, le=100)
    confidence: float = Field(default=0.8, ge=0, le=1)
    metadata: Dict = Field(default_factory=dict)


class SignalResponse(ExternalSignal):
    """Response model for signals (same as ExternalSignal)."""
    pass

class LeadershipSignalMetrics(BaseModel):
    """Detailed metrics for leadership signal analysis."""
    
    # Compensation metrics
    tech_comp_metrics_found: List[str] = Field(default_factory=list)
    tech_comp_score: float = Field(ge=0, le=100, default=0)
    
    # Strategy metrics
    ai_strategy_statements: List[str] = Field(default_factory=list)
    ai_strategy_score: float = Field(ge=0, le=100, default=0)
    
    # Investment metrics
    tech_investment_mentions: List[str] = Field(default_factory=list)
    tech_investment_score: float = Field(ge=0, le=100, default=0)
    
    # Risk metrics
    ai_risk_factors: List[str] = Field(default_factory=list)
    ai_risk_score: float = Field(ge=0, le=100, default=0)
    
    # Overall
    composite_score: float = Field(ge=0, le=100, default=0)
    confidence: float = Field(ge=0, le=1, default=0.7)
    
    # Evidence tracking
    filings_analyzed: int = 0
    total_sections: int = 0


class LeadershipEvidence(BaseModel):
    """A single piece of leadership evidence."""
    evidence_type: str  # 'compensation', 'strategy', 'investment', 'risk'
    text_snippet: str
    filing_type: str
    section: str
    confidence: float
    keywords_matched: List[str]
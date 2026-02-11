# from pydantic import BaseModel, Field
# from typing import List, Dict
# from uuid import UUID
# from datetime import datetime


# class BoardMember(BaseModel):
#     """Single board member or executive"""
#     name: str
#     title: str
#     committees: List[str] = Field(default_factory=list)
#     bio: str = ""
#     is_independent: bool = False
#     tenure_years: int = 0


# class GovernanceSignal(BaseModel):
#     """Board-derived governance indicators"""
#     company_id: UUID
#     ticker: str
    
#     has_tech_committee: bool
#     has_ai_expertise: bool
#     has_data_officer: bool
#     has_risk_tech_oversight: bool
#     has_ai_in_strategy: bool
    
#     tech_expertise_count: int
#     independent_ratio: float = Field(ge=0, le=1)
    
#     governance_score: float = Field(ge=0, le=100)
#     confidence: float = Field(ge=0, le=1)
    
#     ai_experts: List[str] = Field(default_factory=list)
#     relevant_committees: List[str] = Field(default_factory=list)
    
#     analyzed_at: datetime = Field(default_factory=datetime.now)
    
#     class Config:
#         from_attributes = True


from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from uuid import UUID
from datetime import datetime


class BoardMember(BaseModel):
    """Individual board member or executive"""
    name: str
    title: str
    committees: List[str] = Field(default_factory=list)
    bio: str = ""
    is_independent: bool = False
    tenure_years: int = 0
    has_ai_background: bool = False
    ai_keywords_found: List[str] = Field(default_factory=list)


class GovernanceSignal(BaseModel):
    """Board-derived governance indicators"""
    company_id: UUID
    ticker: str
    
    has_tech_committee: bool
    has_ai_expertise: bool
    has_data_officer: bool
    has_risk_tech_oversight: bool
    has_ai_in_strategy: bool
    
    tech_expertise_count: int
    independent_ratio: float = Field(ge=0, le=1)
    
    governance_score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    
    ai_experts: List[str] = Field(default_factory=list)
    relevant_committees: List[str] = Field(default_factory=list)
    
    board_members: List[BoardMember] = Field(default_factory=list)
    
    analyzed_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        from_attributes = True
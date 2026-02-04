class AIIndicatorType(str, Enum):
    """Types of AI background indicators"""
    CHIEF_AI_OFFICER = "chief_ai_officer"
    AI_COMPANY_VETERAN = "ai_company_veteran"
    PHD_AI_ML = "phd_ai_ml"
    AI_ROLE_TITLE = "ai_role_title"
    TECH_LEADERSHIP = "tech_leadership"
    AI_KEYWORDS_ONLY = "ai_keywords_only"


class AIIndicator(BaseModel):
    """Single AI background indicator"""
    type: AIIndicatorType
    evidence: str
    score: float = Field(ge=0, le=1)
    source: str
    confidence: float = Field(default=0.8, ge=0, le=1)


class ExecutiveProfile(BaseModel):
    """Executive with AI background analysis"""
    name: str
    title: str
    role_weight: float = Field(ge=0, le=1)
    indicators: List[AIIndicator] = Field(default_factory=list)
    max_indicator_score: float = Field(default=0.0, ge=0, le=1)
    sources: List[str] = Field(default_factory=list)
    
    def calculate_max_score(self):
        """Calculate max indicator score"""
        if not self.indicators:
            self.max_indicator_score = 0.0
        else:
            self.max_indicator_score = max(ind.score for ind in self.indicators)
        return self.max_indicator_score


class LeadershipEvidence(BaseModel):
    """Complete leadership evidence for a company"""
    ticker: str
    company_name: str
    research_date: datetime
    executives: List[ExecutiveProfile]
    sources_used: List[str]
    total_sources: int
    
    def calculate_leadership_score(self) -> float:
        """Calculate weighted leadership score (0-100)"""
        if not self.executives:
            return 0.0
        
        total_weighted = sum(
            exec.role_weight * exec.max_indicator_score 
            for exec in self.executives
        )
        total_weight = sum(exec.role_weight for exec in self.executives)
        
        if total_weight == 0:
            return 0.0
        
        return (total_weighted / total_weight) * 100


class LeadershipSignalMetrics(BaseModel):
    """Detailed metrics for leadership signal analysis"""
    
    # Website metrics
    executives_found: int = 0
    website_score: float = Field(ge=0, le=100, default=0.0)
    
    # News metrics
    news_articles_found: int = 0
    news_bonus: float = Field(ge=0, le=10, default=0.0)
    
    # Overall
    composite_score: float = Field(ge=0, le=100, default=0.0)
    confidence: float = Field(ge=0, le=1, default=0.7)
    
    # Evidence tracking
    sources_attempted: int = 0
    sources_successful: int = 0
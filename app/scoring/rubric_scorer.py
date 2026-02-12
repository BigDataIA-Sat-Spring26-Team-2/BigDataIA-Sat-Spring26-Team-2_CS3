from dataclasses import dataclass
from typing import Dict, List, Tuple
from enum import Enum
from decimal import Decimal


class ScoreLevel(Enum):
    LEVEL_5 = (80, 100, "Excellent")
    LEVEL_4 = (60, 79, "Good")
    LEVEL_3 = (40, 59, "Adequate")
    LEVEL_2 = (20, 39, "Developing")
    LEVEL_1 = (0, 19, "Nascent")
    
    @property
    def min_score(self) -> int:
        return self.value[0]
    
    @property
    def max_score(self) -> int:
        return self.value[1]
    
    @property
    def label(self) -> str:
        return self.value[2]


@dataclass
class RubricCriteria:
    level: ScoreLevel
    keywords: List[str]
    min_keyword_matches: int
    quantitative_threshold: float


@dataclass
class RubricResult:
    dimension: str
    level: ScoreLevel
    score: Decimal
    matched_keywords: List[str]
    keyword_match_count: int
    confidence: Decimal
    rationale: str

class RubricScorer:
    
    def __init__(self):
        self.dimension_scorers = {
            'data_infrastructure': self._score_data_infrastructure,
            'ai_governance': self._score_ai_governance,
            #add other dimensions
        }
    
    def score_dimension(
        self,
        dimension: str,
        evidence_text: str,
        quantitative_metrics: Dict[str, float],
    ) -> RubricResult:
        scorer_method = self.dimension_scorers.get(dimension)
        
        if not scorer_method:
            return self._default_score(dimension)
        
        return scorer_method(evidence_text, quantitative_metrics)
    
    def _match_keywords(
        self, 
        text: str, 
        keywords: List[str]
    ) -> Tuple[List[str], int]:
        text_lower = text.lower()
        matches = [kw for kw in keywords if kw.lower() in text_lower]
        return matches, len(matches)
    
    def _interpolate_score(
        self,
        level: ScoreLevel,
        match_ratio: float
    ) -> Decimal:

        min_score = level.min_score
        max_score = level.max_score
        
        # Linear interpolation: more matches = higher in range
        interpolated = min_score + (max_score - min_score) * match_ratio
        
        return Decimal(str(round(interpolated, 1)))
    
    def _check_quantitative(
        self,
        dimension: str,
        metrics: Dict[str, float],
        threshold: float
    ) -> bool:
        if dimension == "data_infrastructure":
            return metrics.get("data_quality_score", 0) >= threshold
        
        elif dimension == "talent":
            return metrics.get("ai_job_ratio", 0) >= threshold
        
        elif dimension == "use_case_portfolio":
            return metrics.get("production_use_cases", 0) >= threshold
        
        elif dimension == "technology_stack":
            return metrics.get("mlops_maturity", 0) >= threshold
        
        return True
    
    def _evaluate_rubric(
        self,
        dimension: str,
        rubric: Dict[ScoreLevel, RubricCriteria],
        evidence_text: str,
        quantitative_metrics: Dict[str, float]
    ) -> RubricResult:
        text = evidence_text.lower()
        
        # Check levels from highest to lowest
        for level in [ScoreLevel.LEVEL_5, ScoreLevel.LEVEL_4, 
                      ScoreLevel.LEVEL_3, ScoreLevel.LEVEL_2, 
                      ScoreLevel.LEVEL_1]:
            
            criteria = rubric.get(level)
            if not criteria:
                continue
            
            # Match keywords
            matches, match_count = self._match_keywords(text, criteria.keywords)
            
            # Check minimum keyword requirement
            if match_count >= criteria.min_keyword_matches:
                
                # Check quantitative threshold
                meets_quantitative = self._check_quantitative(
                    dimension, 
                    quantitative_metrics, 
                    criteria.quantitative_threshold
                )
                
                if meets_quantitative:
                    # Calculate score within this level
                    match_ratio = match_count / len(criteria.keywords) if len(criteria.keywords) > 0 else 0
                    score = self._interpolate_score(level, match_ratio)
                    
                    return RubricResult(
                        dimension=dimension,
                        level=level,
                        score=score,
                        matched_keywords=matches,
                        keyword_match_count=match_count,
                        confidence=Decimal("0.85"),
                        rationale=f"Matched {match_count}/{len(criteria.keywords)} keywords at {level.label} level"
                    )
        
        # No level matched → return lowest score
        return RubricResult(
            dimension=dimension,
            level=ScoreLevel.LEVEL_1,
            score=Decimal("10.0"),
            matched_keywords=[],
            keyword_match_count=0,
            confidence=Decimal("0.6"),
            rationale="No rubric criteria met"
        )
    
    def _default_score(self, dimension: str) -> RubricResult:
        return RubricResult(
            dimension=dimension,
            level=ScoreLevel.LEVEL_3,
            score=Decimal("50.0"),
            matched_keywords=[],
            keyword_match_count=0,
            confidence=Decimal("0.5"),
            rationale="Default score - dimension not recognized"
        )
    

    # Dimension 1 : DATA INFRASTRUCTURE
    def _get_data_infrastructure_rubric(self) -> Dict[ScoreLevel, RubricCriteria]:
        return {
            ScoreLevel.LEVEL_5: RubricCriteria(
                level=ScoreLevel.LEVEL_5,
                keywords=[
                    "snowflake", "databricks", "lakehouse", "real-time",
                    "api-first", "modern cloud", "data mesh", "streaming",
                    "event-driven", "microservices", "data platform",
                    "cloud-native", "serverless"
                ],
                min_keyword_matches=3,
                quantitative_threshold=0.90,
            ),
            ScoreLevel.LEVEL_4: RubricCriteria(
                level=ScoreLevel.LEVEL_4,
                keywords=[
                    "azure", "aws", "gcp", "warehouse", "etl",
                    "batch pipelines", "hybrid cloud", "data catalog",
                    "cloud data", "data lake", "redshift", "bigquery",
                    "s3", "azure data lake", "mlops", "airflow"
                ],
                min_keyword_matches=2,
                quantitative_threshold=0.70,
            ),
            ScoreLevel.LEVEL_3: RubricCriteria(
                level=ScoreLevel.LEVEL_3,
                keywords=[
                    "migration", "hybrid", "modernizing", "cloud adoption",
                    "roadmap", "transitioning", "upgrading", "pilot",
                    "cloud strategy", "apache spark", "spark", "hadoop",
                    "data processing", "docker", "kubernetes"
                ],
                min_keyword_matches=2,
                quantitative_threshold=0.40,
            ),
            ScoreLevel.LEVEL_2: RubricCriteria(
                level=ScoreLevel.LEVEL_2,
                keywords=[
                    "legacy", "silos", "on-premise", "siloed",
                    "traditional infrastructure", "limited integration",
                    "on-prem", "fragmented"
                ],
                min_keyword_matches=1,
                quantitative_threshold=0.20,
            ),
            ScoreLevel.LEVEL_1: RubricCriteria(
                level=ScoreLevel.LEVEL_1,
                keywords=[
                    "mainframe", "spreadsheets", "manual", "no infrastructure",
                    "fragmented", "outdated systems", "no platform",
                    "paper-based", "unstructured", "excel-based",
                    "manual processes"
                ],
                min_keyword_matches=1,
                quantitative_threshold=0.0,
            ),
        }
    
    def _score_data_infrastructure(
        self,
        evidence_text: str,
        quantitative_metrics: Dict[str, float]
    ) -> RubricResult:

        rubric = self._get_data_infrastructure_rubric()
        
        result = self._evaluate_rubric(
            dimension="data_infrastructure",
            rubric=rubric,
            evidence_text=evidence_text,
            quantitative_metrics=quantitative_metrics
        )
        
        if result.keyword_match_count >= 5:
            result.confidence = min(Decimal("0.95"), result.confidence + Decimal("0.10"))
        
        return result
    

    # Dimension 2 : AI GOVERNANCE
    def _score_ai_governance(
        self,
        evidence_text: str,
        quantitative_metrics: Dict[str, float]
    ) -> RubricResult:
        rubric = self._get_ai_governance_rubric()
        
        return self._evaluate_rubric(
            dimension="ai_governance",
            rubric=rubric,
            evidence_text=evidence_text,
            quantitative_metrics=quantitative_metrics
        )
   
    def _get_ai_governance_rubric(self) -> Dict[ScoreLevel, RubricCriteria]:
        return {
            ScoreLevel.LEVEL_5: RubricCriteria(
                level=ScoreLevel.LEVEL_5,
                keywords=[
                    "caio", "cdo", "board committee", "model risk",
                    "chief ai officer", "chief data officer",
                    "ai governance framework", "board ai committee",
                    "comprehensive framework", "model risk management",
                    "ai ethics board", "responsible ai"
                ],
                min_keyword_matches=3,
                quantitative_threshold=0.0,
            ),
            ScoreLevel.LEVEL_4: RubricCriteria(
                level=ScoreLevel.LEVEL_4,
                keywords=[
                    "vp data", "ai policy", "risk framework",
                    "documented policies", "risk assessment",
                    "vp ai", "ai governance", "model governance",
                    "data governance", "compliance framework"
                ],
                min_keyword_matches=2,
                quantitative_threshold=0.0,
            ),
            ScoreLevel.LEVEL_3: RubricCriteria(
                level=ScoreLevel.LEVEL_3,
                keywords=[
                    "director", "guidelines", "it governance",
                    "basic policies", "director level ownership",
                    "policy exists", "it-led governance"
                ],
                min_keyword_matches=2,
                quantitative_threshold=0.0,
            ),
            ScoreLevel.LEVEL_2: RubricCriteria(
                level=ScoreLevel.LEVEL_2,
                keywords=[
                    "informal", "no policy", "ad-hoc",
                    "informal governance", "ad-hoc oversight",
                    "no documented"
                ],
                min_keyword_matches=1,
                quantitative_threshold=0.0,
            ),
            ScoreLevel.LEVEL_1: RubricCriteria(
                level=ScoreLevel.LEVEL_1,
                keywords=[
                    "none", "no oversight", "unmanaged",
                    "no governance", "no ai oversight",
                    "unmanaged risk"
                ],
                min_keyword_matches=1,
                quantitative_threshold=0.0,
            ),
        }
   
   # ========================================
    # DIMENSION 4: Talent
    # =======================================

    
    def _get_talent_rubric(self) -> Dict[ScoreLevel, RubricCriteria]:
        """
        Rubric for Talent dimension.
        
        Evaluates:
        - AI/ML team size (>20 specialists = excellent)
        - Retention and turnover (<10% = excellent)
        - Hiring pipeline (active recruiting)
        - Technical depth (senior/principal engineers)
        """
        return {
            ScoreLevel.LEVEL_5: RubricCriteria(
                level=ScoreLevel.LEVEL_5,
                keywords=[
                    "ml platform", "ai research", "large team",
                    ">20 specialists", "ai leadership", "principal ml",
                    "staff ml", "research capability", "ml platform team",
                    "internal research", "principal engineer", "staff engineer",
                    "low turnover", "ml research"
                ],
                min_keyword_matches=3,
                quantitative_threshold=0.40,  # >40% AI job ratio
            ),
            ScoreLevel.LEVEL_4: RubricCriteria(
                level=ScoreLevel.LEVEL_4,
                keywords=[
                    "data science team", "ml engineers", "10-20 professionals",
                    "active hiring", "retention programs", "established team",
                    "senior ml", "lead data scientist", "growing team",
                    "hiring pipeline", "senior data scientist"
                ],
                min_keyword_matches=2,
                quantitative_threshold=0.25,
            ),
            ScoreLevel.LEVEL_3: RubricCriteria(
                level=ScoreLevel.LEVEL_3,
                keywords=[
                    "data scientist", "growing team", "small team",
                    "3-10 data scientists", "building capability",
                    "some turnover", "developing team", "ml engineer"
                ],
                min_keyword_matches=2,
                quantitative_threshold=0.15,
            ),
            ScoreLevel.LEVEL_2: RubricCriteria(
                level=ScoreLevel.LEVEL_2,
                keywords=[
                    "junior", "contractor", "turnover",
                    "1-2 data scientists", "high turnover",
                    "limited depth", "contract workers"
                ],
                min_keyword_matches=1,
                quantitative_threshold=0.05,
            ),
            ScoreLevel.LEVEL_1: RubricCriteria(
                level=ScoreLevel.LEVEL_1,
                keywords=[
                    "no data scientist", "vendor only", "outsourced",
                    "no ai talent", "consultants only"
                ],
                min_keyword_matches=1,
                quantitative_threshold=0.0,
            ),
        }
    
    def _score_talent(
        self,
        evidence_text: str,
        quantitative_metrics: Dict[str, float]
    ) -> RubricResult:
        """
        Score Talent dimension.
        
        Evidence sources:
        - technology_hiring (70% weight) - job postings
        - glassdoor_reviews (10% weight) - employee feedback
        
        Quantitative metrics:
        - ai_job_ratio: AI jobs / total tech jobs
        - team_size: Total AI specialists
        """
        rubric = self._get_talent_rubric()
        
        return self._evaluate_rubric(
            dimension="talent",
            rubric=rubric,
            evidence_text=evidence_text,
            quantitative_metrics=quantitative_metrics
        )
    


   # ========================================
    # DIMENSION 6: USE CASE PORTFOLIO
    # =======================================

def _get_use_case_portfolio_rubric(self) -> Dict[ScoreLevel, RubricCriteria]:
        """
        Rubric for Use Case Portfolio dimension.
        
        Evaluates:
        - Production AI deployments (5+ use cases = excellent)
        - ROI tracking and measurement (3x+ ROI documented)
        - Use case diversity across business functions
        - Scaling plans and roadmap
        """
        return {
            ScoreLevel.LEVEL_5: RubricCriteria(
                level=ScoreLevel.LEVEL_5,
                keywords=[
                    "production ai", "3x roi", "ai product",
                    "5+ use cases", "revenue-generating",
                    "documented roi", "production deployments",
                    "ai products", "measurable roi", "deployed models"
                ],
                min_keyword_matches=3,
                quantitative_threshold=5.0,  # 5+ production use cases
            ),
            ScoreLevel.LEVEL_4: RubricCriteria(
                level=ScoreLevel.LEVEL_4,
                keywords=[
                    "production", "measured roi", "scaling",
                    "2-4 use cases", "positive roi", "scaling plans",
                    "in production", "deployed models", "use cases"
                ],
                min_keyword_matches=2,
                quantitative_threshold=2.0,  # 2-4 use cases
            ),
            ScoreLevel.LEVEL_3: RubricCriteria(
                level=ScoreLevel.LEVEL_3,
                keywords=[
                    "pilot", "early production", "1-2 pilots",
                    "early roi", "pilot to production",
                    "roi tracking underway", "use case"
                ],
                min_keyword_matches=2,
                quantitative_threshold=1.0,  # 1-2 use cases
            ),
            ScoreLevel.LEVEL_2: RubricCriteria(
                level=ScoreLevel.LEVEL_2,
                keywords=[
                    "poc", "proof of concept", "no production",
                    "pocs only", "experiments", "prototype"
                ],
                min_keyword_matches=1,
                quantitative_threshold=0.0,
            ),
            ScoreLevel.LEVEL_1: RubricCriteria(
                level=ScoreLevel.LEVEL_1,
                keywords=[
                    "exploring", "no use cases", "exploration phase",
                    "no ai projects", "planning only"
                ],
                min_keyword_matches=1,
                quantitative_threshold=0.0,
            ),
        }
    
def _score_use_case_portfolio(
        self,
        evidence_text: str,
        quantitative_metrics: Dict[str, float]
    ) -> RubricResult:
        """
        Score Use Case Portfolio dimension.
        
        Evidence sources:
        - SEC Item 1 (70% weight) - Business section, product mentions
        - innovation_activity (30% weight) - patents on applications
        - SEC Item 7 (30% weight) - MD&A project ROI discussion
        """
        rubric = self._get_use_case_portfolio_rubric()
        
        return self._evaluate_rubric(
            dimension="use_case_portfolio",
            rubric=rubric,
            evidence_text=evidence_text,
            quantitative_metrics=quantitative_metrics
        )
    
    # ========================================
    # DIMENSION 7: CULTURE
    # ========================================
    
def _get_culture_rubric(self) -> Dict[ScoreLevel, RubricCriteria]:
        """
        Rubric for Culture dimension.
        
        Evaluates:
        - Innovation culture (celebrated, rewarded)
        - Data-driven decision making (metrics-based)
        - Change readiness (agile, adaptive)
        - Experimentation mindset (fail-fast encouraged)
        """
        return {
            ScoreLevel.LEVEL_5: RubricCriteria(
                level=ScoreLevel.LEVEL_5,
                keywords=[
                    "innovative", "data-driven", "fail-fast",
                    "innovation celebrated", "experimentation culture",
                    "rewarded", "embedded decisions", "data culture",
                    "agile", "iterative", "cutting-edge"
                ],
                min_keyword_matches=3,
                quantitative_threshold=0.0,
            ),
            ScoreLevel.LEVEL_4: RubricCriteria(
                level=ScoreLevel.LEVEL_4,
                keywords=[
                    "experimental", "learning culture", "encouraged",
                    "experimentation encouraged", "data literacy",
                    "growing culture", "open to innovation"
                ],
                min_keyword_matches=2,
                quantitative_threshold=0.0,
            ),
            ScoreLevel.LEVEL_3: RubricCriteria(
                level=ScoreLevel.LEVEL_3,
                keywords=[
                    "open to change", "some resistance",
                    "mixed adoption", "middle management resistance",
                    "gradual change"
                ],
                min_keyword_matches=2,
                quantitative_threshold=0.0,
            ),
            ScoreLevel.LEVEL_2: RubricCriteria(
                level=ScoreLevel.LEVEL_2,
                keywords=[
                    "bureaucratic", "resistant", "slow",
                    "change resistant", "hierarchical",
                    "intuition over data", "traditional"
                ],
                min_keyword_matches=1,
                quantitative_threshold=0.0,
            ),
            ScoreLevel.LEVEL_1: RubricCriteria(
                level=ScoreLevel.LEVEL_1,
                keywords=[
                    "hostile", "siloed", "no data culture",
                    "hostile to change", "rigid organization",
                    "no innovation"
                ],
                min_keyword_matches=1,
                quantitative_threshold=0.0,
            ),
        }
    
def _score_culture(
        self,
        evidence_text: str,
        quantitative_metrics: Dict[str, float]
    ) -> RubricResult:
        """
        Score Culture dimension.
        
        Evidence sources:
        - glassdoor_reviews (80% weight) - PRIMARY - Task 5.0c
        - leadership_signals (10% weight)
        - technology_hiring (10% weight) - job descriptions
        """
        rubric = self._get_culture_rubric()
        
        return self._evaluate_rubric(
            dimension="culture",
            rubric=rubric,
            evidence_text=evidence_text,
            quantitative_metrics=quantitative_metrics
        )

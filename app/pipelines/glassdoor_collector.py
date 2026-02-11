import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from decimal import Decimal

logger = logging.getLogger(__name__)


@dataclass
class GlassdoorReview:
    review_id: str
    rating: float
    title: str
    pros: str
    cons: str
    advice_to_management: Optional[str]
    is_current_employee: bool
    job_title: str
    review_date: datetime


@dataclass
class CultureSignal:
    company_id: str
    ticker: str
    innovation_score: Decimal
    data_driven_score: Decimal
    change_readiness_score: Decimal
    ai_awareness_score: Decimal
    overall_score: Decimal
    review_count: int
    avg_rating: Decimal
    confidence: Decimal


class GlassdoorCultureCollector:
    
    INNOVATION_POSITIVE = [
        "innovative", "cutting-edge", "forward-thinking",
        "encourages new ideas", "experimental", "creative freedom",
        "startup mentality", "move fast", "disruptive",
        "innovation", "pioneering", "leading edge"
    ]
    
    INNOVATION_NEGATIVE = [
        "bureaucratic", "slow to change", "resistant",
        "outdated", "stuck in old ways", "red tape",
        "politics", "siloed", "hierarchical",
        "legacy mindset", "conservative", "risk-averse"
    ]
    
    DATA_DRIVEN_KEYWORDS = [
        "data-driven", "metrics", "evidence-based",
        "analytical", "kpis", "dashboards", "data culture",
        "measurement", "quantitative", "analytics",
        "data informed", "metrics driven"
    ]
    
    AI_AWARENESS_KEYWORDS = [
        "ai", "artificial intelligence", "machine learning",
        "automation", "data science", "ml", "algorithms",
        "predictive", "neural network", "deep learning",
        "nlp", "computer vision"
    ]
    
    CHANGE_POSITIVE = [
        "agile", "adaptive", "fast-paced", "embraces change",
        "continuous improvement", "growth mindset",
        "flexible", "dynamic", "responsive"
    ]
    
    CHANGE_NEGATIVE = [
        "rigid", "traditional", "slow", "risk-averse",
        "change resistant", "old school", "inflexible",
        "status quo", "stagnant"
    ]
    
    COMPANY_GLASSDOOR_URLS = {
        "WMT": "https://www.glassdoor.com/Reviews/Walmart-Reviews-E715.htm",
        "JPM": "https://www.glassdoor.com/Reviews/JPMorgan-Chase-and-Co-Reviews-E145.htm",
        "GS": "https://www.glassdoor.com/Reviews/Goldman-Sachs-Reviews-E2800.htm",
        "TGT": "https://www.glassdoor.com/Reviews/Target-Reviews-E194.htm",
        "CAT": "https://www.glassdoor.com/Reviews/Caterpillar-Reviews-E14583.htm",
        "DE": "https://www.glassdoor.com/Reviews/Deere-and-Company-Reviews-E1239.htm",
        "UNH": "https://www.glassdoor.com/Reviews/UnitedHealth-Group-Reviews-E1513.htm",
        "HCA": "https://www.glassdoor.com/Reviews/HCA-Healthcare-Reviews-E14106.htm",
        "ADP": "https://www.glassdoor.com/Reviews/ADP-Reviews-E737.htm",
        "PAYX": "https://www.glassdoor.com/Reviews/Paychex-Reviews-E3301.htm",
    }
    


from dataclasses import dataclass
from typing import List
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
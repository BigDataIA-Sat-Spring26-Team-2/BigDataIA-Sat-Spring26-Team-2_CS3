from decimal import Decimal
from typing import NamedTuple, Dict
import math
import structlog

from app.scoring.utils import to_decimal, clamp

logger = structlog.get_logger()


class ConfidenceResult(NamedTuple):
    score: Decimal
    confidence: Decimal  
    sem: Decimal  
    ci_lower: Decimal
    ci_upper: Decimal 
    evidence_count: int 
    score_type: str  
    
    def get_summary(self) -> dict:
        return {
            "score": float(self.score),
            "confidence": float(self.confidence),
            "sem": float(self.sem),
            "ci_lower": float(self.ci_lower),
            "ci_upper": float(self.ci_upper),
            "ci_width": float(self.ci_upper - self.ci_lower),
            "evidence_count": self.evidence_count,
            "score_type": self.score_type
        }


class ConfidenceCalculator:
    """
    Calculate confidence intervals using SEM and Spearman-Brown reliability.
        ρ = (n × r) / (1 + (n - 1) × r)
    
    Where:
        - n: Number of evidence sources
        - r: Average inter-item correlation (estimated)
        - ρ: Composite reliability
    
    Then SEM is calculated as:
        SEM = σ × √(1 - ρ)
    
    Where σ is the population standard deviation (estimated from score type).
    
    Finally, 95% confidence interval:
        CI = score ± 1.96 × SEM
    """

    SIGMA_ESTIMATES: Dict[str, float] = {
        "vr": 15.0,  # V^R scores have moderate variance
        "hr": 12.0,  # H^R scores are more stable (industry-level)
        "synergy": 18.0,  # Synergy has higher variance
        "org_air": 14.0,  # Final Org-AI-R composite
        "dimension": 20.0,  # Individual dimensions have highest variance
    }
    
    # Average inter-item correlation estimate
    # Higher r = evidence sources are more correlated
    # Lower r = evidence sources are more independent
    AVERAGE_CORRELATION = 0.65  # Moderate correlation assumption
    
    # Z-score for 95% confidence interval
    Z_95 = 1.96
    
    def calculate(
        self,
        score: float,
        score_type: str,
        evidence_count: int,
        average_correlation: float = None,
    ) -> ConfidenceResult:
        """
        Calculate confidence interval for a score.
        
        Args:
            score: The score to calculate confidence for (0-100)
            score_type: Type of score ("vr", "hr", "synergy", "org_air", "dimension")
            evidence_count: Number of evidence sources used
            average_correlation: Override default correlation (0-1)
        
        Returns:
            ConfidenceResult with confidence interval

        """
        logger.info(
            "confidence_calculation_started",
            score=score,
            score_type=score_type,
            evidence_count=evidence_count
        )
        
        # VALIDATION
        if not (0 <= score <= 100):
            raise ValueError(f"Score must be in [0, 100], got {score}")
        
        if evidence_count < 1:
            raise ValueError(f"Evidence count must be >= 1, got {evidence_count}")
        
        if score_type not in self.SIGMA_ESTIMATES:
            logger.warning(
                "unknown_score_type_using_default",
                score_type=score_type,
                available_types=list(self.SIGMA_ESTIMATES.keys())
            )
            score_type = "org_air"  # Use default
        
        # Use provided correlation or default
        r = average_correlation if average_correlation is not None else self.AVERAGE_CORRELATION
        
        if not (0 <= r <= 1):
            raise ValueError(f"Correlation must be in [0, 1], got {r}")
        
        # Convert to Decimal
        score_dec = to_decimal(score, places=2)
        n = evidence_count
        r_dec = to_decimal(r, places=4)
        
        # STEP 1: Get population standard deviation estimate
        sigma = to_decimal(self.SIGMA_ESTIMATES[score_type], places=2)
        
        # STEP 2: Calculate Spearman-Brown reliability (ρ)
        # ρ = (n × r) / (1 + (n - 1) × r)
        numerator = to_decimal(n, places=0) * r_dec
        denominator = Decimal("1") + (to_decimal(n - 1, places=0) * r_dec)
        
        if denominator == 0:
            rho = Decimal("0")
        else:
            rho = numerator / denominator
        
        # Clamp to [0, 1]
        rho = clamp(rho, min_val=Decimal("0"), max_val=Decimal("1"))
        
        # STEP 3: Calculate SEM
        # SEM = σ × √(1 - ρ)
        one_minus_rho = Decimal("1") - rho
        
        # Use Python's math.sqrt for the calculation, then convert to Decimal
        sem_float = float(sigma) * math.sqrt(max(0, float(one_minus_rho)))
        sem = to_decimal(sem_float, places=2)
        
        # STEP 4: Calculate 95% confidence interval
        # CI = score ± 1.96 × SEM
        z_score = to_decimal(self.Z_95, places=2)
        margin = z_score * sem
        
        ci_lower_raw = score_dec - margin
        ci_upper_raw = score_dec + margin
        
        # STEP 5: Clamp CI to valid score range [0, 100]
        ci_lower = clamp(ci_lower_raw, min_val=Decimal("0"), max_val=Decimal("100"))
        ci_upper = clamp(ci_upper_raw, min_val=Decimal("0"), max_val=Decimal("100"))
        
        logger.info(
            "confidence_calculation_completed",
            rho=float(rho),
            sem=float(sem),
            ci_lower=float(ci_lower),
            ci_upper=float(ci_upper),
            ci_width=float(ci_upper - ci_lower)
        )
        
        # Build result
        result = ConfidenceResult(
            score=score_dec,
            confidence=rho,
            sem=sem,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            evidence_count=evidence_count,
            score_type=score_type
        )
        
        logger.info("confidence_result_summary", summary=result.get_summary())
        
        return result

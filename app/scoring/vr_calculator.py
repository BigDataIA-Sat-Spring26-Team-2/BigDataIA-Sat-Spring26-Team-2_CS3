"""
Task 5.2: V^R (Venture Readiness) Calculator

Implements the core V^R formula from Case Study 1, Equation 1:

    V^R = D̄_w × (1 - λ × CV_D) × TalentRiskAdj

Where:
- D̄_w = Weighted mean of 7 dimension scores (sector-specific weights)
- λ = 0.25 (non-compensatory penalty coefficient)  
- CV_D = Coefficient of variation (measures dimensional imbalance)
- TalentRiskAdj = 1 - 0.15 × max(0, TC - 0.25)

IMPORTANT: This calculator is INPUT-AGNOSTIC
- Works with Path A scores only (current)
- Works with Path B scores only
- Works with combined (Path A + Path B) / 2 (future)
- Just pass it 7 dimension scores - doesn't care where they came from!
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict
import structlog

from app.scoring.utils import (
    weighted_mean,
    weighted_std_dev,
    coefficient_of_variation,
    clamp,
    to_decimal
)

logger = structlog.get_logger()


@dataclass
class VRResult:
    """
    Complete V^R calculation result with full audit trail.
    
    Provides transparency into how the final score was calculated.
    All components are exposed for debugging and business reporting.
    """
    # Final score
    vr_score: Decimal  # 0-100
    
    # Main components
    weighted_mean: Decimal  # D̄_w (base score before penalties)
    cv: Decimal  # Coefficient of variation
    cv_penalty: Decimal  # 1 - 0.25 × CV
    talent_concentration: Decimal  # TC input (0-1)
    talent_risk_adj: Decimal  # 1 - 0.15 × max(0, TC - 0.25)
    
    # Context
    sector: str
    dimension_scores: Dict[str, Decimal]  # All 7 dimension scores used
    dimension_weights: Dict[str, Decimal]  # Sector weights applied
    
    # Penalty breakdown (for reporting)
    base_score: Decimal  # Same as weighted_mean
    cv_penalty_amount: Decimal  # Points lost to CV penalty
    tc_penalty_amount: Decimal  # Points lost to TC penalty
    
    def get_summary(self) -> str:
        """Human-readable summary of V^R calculation"""
        return (
            f"V^R = {self.vr_score:.1f}/100\n"
            f"  Base (weighted mean): {self.weighted_mean:.2f}\n"
            f"  CV penalty ({float(self.cv):.1%} variation): ×{self.cv_penalty:.4f} "
            f"(-{self.cv_penalty_amount:.1f} pts)\n"
            f"  TC penalty ({float(self.talent_concentration):.1%} concentration): ×{self.talent_risk_adj:.4f} "
            f"(-{self.tc_penalty_amount:.1f} pts)\n"
            f"  Sector: {self.sector}"
        )


class VRCalculator:
    """
    Calculate V^R (Venture Readiness) score.
    
    This is Phase 5 of the scoring pipeline that combines 7 dimension scores
    into a single metric with penalties for imbalance and talent concentration.
    """
    
    # Sector-Specific Dimension Weights (from Case Study 1, Table 1)
    # Different industries value different capabilities
    SECTOR_WEIGHTS: Dict[str, Dict[str, Decimal]] = {
        "technology": {
            "data_infrastructure": Decimal("0.25"),
            "ai_governance": Decimal("0.15"),  # Lower (less regulation)
            "technology_stack": Decimal("0.20"),  # Higher (core capability)
            "talent": Decimal("0.20"),  # Higher (talent war)
            "leadership": Decimal("0.10"),
            "use_case_portfolio": Decimal("0.05"),
            "culture": Decimal("0.05"),
        },
        "financial_services": {
            "data_infrastructure": Decimal("0.25"),
            "ai_governance": Decimal("0.25"),  # Higher (heavy regulation)
            "technology_stack": Decimal("0.15"),
            "talent": Decimal("0.15"),
            "leadership": Decimal("0.10"),
            "use_case_portfolio": Decimal("0.05"),
            "culture": Decimal("0.05"),
        },
        "healthcare": {
            "data_infrastructure": Decimal("0.25"),
            "ai_governance": Decimal("0.25"),  # Higher (HIPAA, compliance)
            "technology_stack": Decimal("0.15"),
            "talent": Decimal("0.15"),
            "leadership": Decimal("0.10"),
            "use_case_portfolio": Decimal("0.05"),
            "culture": Decimal("0.05"),
        },
        "retail": {
            "data_infrastructure": Decimal("0.25"),
            "ai_governance": Decimal("0.15"),
            "technology_stack": Decimal("0.15"),
            "talent": Decimal("0.15"),
            "leadership": Decimal("0.10"),
            "use_case_portfolio": Decimal("0.15"),  # Higher (customer experience)
            "culture": Decimal("0.05"),
        },
        "manufacturing": {
            "data_infrastructure": Decimal("0.25"),
            "ai_governance": Decimal("0.20"),
            "technology_stack": Decimal("0.15"),
            "talent": Decimal("0.15"),
            "leadership": Decimal("0.10"),
            "use_case_portfolio": Decimal("0.10"),
            "culture": Decimal("0.05"),
        },
        "business_services": {
            "data_infrastructure": Decimal("0.25"),
            "ai_governance": Decimal("0.20"),
            "technology_stack": Decimal("0.15"),
            "talent": Decimal("0.15"),
            "leadership": Decimal("0.10"),
            "use_case_portfolio": Decimal("0.10"),
            "culture": Decimal("0.05"),
        },
    }
    
    # Default weights (Case Study 1, Table 1)
    DEFAULT_WEIGHTS = {
        "data_infrastructure": Decimal("0.25"),
        "ai_governance": Decimal("0.20"),
        "technology_stack": Decimal("0.15"),
        "talent": Decimal("0.15"),
        "leadership": Decimal("0.10"),
        "use_case_portfolio": Decimal("0.10"),
        "culture": Decimal("0.05"),
    }
    
    # Formula Constants (from PDF)
    LAMBDA = Decimal("0.25")  # CV penalty coefficient
    TC_THRESHOLD = Decimal("0.25")  # 25% TC threshold
    TC_PENALTY_RATE = Decimal("0.15")  # 15% penalty per unit TC above threshold
    
    def calculate(
        self,
        dimension_scores: Dict[str, float],
        talent_concentration: float,
        sector: str
    ) -> VRResult:
        """
        Calculate V^R score using the framework formula.
        
        This is the MAIN method that implements the V^R formula from PDF.
        
        Args:
            dimension_scores: Dict of 7 dimension scores (0-100)
                             Keys: dimension names (strings)
                             Source: Path A, Path B, or (A+B)/2
            talent_concentration: TC value (0-1)
                                 From TalentConcentrationCalculator
            sector: Company sector (for weight selection)
                   e.g., "manufacturing", "healthcare"
        
        Returns:
            VRResult with complete calculation breakdown
        
        Raises:
            ValueError: If missing dimensions, invalid sector, or invalid scores
        
        Example:
            >>> calculator = VRCalculator()
            >>> scores = {
            ...     "data_infrastructure": 35.2,
            ...     "ai_governance": 7.5,
            ...     "technology_stack": 55.7,
            ...     "talent": 53.4,
            ...     "leadership": 7.5,
            ...     "use_case_portfolio": 80.0,
            ...     "culture": 7.5
            ... }
            >>> result = calculator.calculate(scores, 0.15, "manufacturing")
            >>> print(f"V^R: {result.vr_score:.1f}/100")
        """
        logger.info(
            "vr_calculation_started",
            sector=sector,
            tc=talent_concentration,
            dimension_count=len(dimension_scores)
        )
        
        # Convert inputs to Decimal
        tc = to_decimal(talent_concentration, places=4)
        
        # STEP 1: Get sector-specific weights
        weights = self._get_sector_weights(sector)
        
        # STEP 2: Validate and prepare dimension values
        dimension_values = []
        weight_values = []
        
        # Validate all 7 dimensions are present
        required_dimensions = set(self.DEFAULT_WEIGHTS.keys())
        provided_dimensions = set(dimension_scores.keys())
        
        missing_dimensions = required_dimensions - provided_dimensions
        if missing_dimensions:
            raise ValueError(
                f"Missing required dimensions: {missing_dimensions}. "
                f"V^R requires all 7 dimensions. "
                f"Evidence Mapper should provide all dimensions (defaults to 50.0 if no data)."
            )
        
        for dim_name in self.DEFAULT_WEIGHTS.keys():
            score = dimension_scores[dim_name]
            
            # Validate score is in valid range
            if not (0 <= score <= 100):
                raise ValueError(
                    f"Invalid score for {dim_name}: {score}. "
                    f"Scores must be in range [0, 100]."
                )
            
            dimension_values.append(to_decimal(score, places=2))
            weight_values.append(weights[dim_name])
        
        logger.debug(
            "dimension_scores_prepared",
            scores={k: float(v) for k, v in zip(self.DEFAULT_WEIGHTS.keys(), dimension_values)},
            weights={k: float(v) for k, v in weights.items()}
        )
        
        # STEP 3: Calculate weighted mean (D̄_w)
        mean_score = weighted_mean(dimension_values, weight_values)
        logger.info("weighted_mean_calculated", value=float(mean_score))
        
        # STEP 4: Calculate CV penalty
        std_dev = weighted_std_dev(dimension_values, weight_values, mean_score)
        cv = coefficient_of_variation(std_dev, mean_score)
        cv_penalty = Decimal("1") - self.LAMBDA * cv
        
        # Ensure penalty is in valid range [0, 1]
        cv_penalty = clamp(cv_penalty, Decimal("0"), Decimal("1"))
        
        logger.info(
            "cv_penalty_calculated",
            std_dev=float(std_dev),
            cv=float(cv),
            penalty=float(cv_penalty),
            interpretation=self._interpret_cv(cv)
        )
        
        # STEP 5: Calculate Talent Risk Adjustment
        tc_excess = max(Decimal("0"), tc - self.TC_THRESHOLD)
        talent_risk_adj = Decimal("1") - self.TC_PENALTY_RATE * tc_excess
        
        # Ensure adjustment is in valid range [0, 1]
        talent_risk_adj = clamp(talent_risk_adj, Decimal("0"), Decimal("1"))
        
        logger.info(
            "talent_risk_calculated",
            tc=float(tc),
            tc_threshold=float(self.TC_THRESHOLD),
            tc_excess=float(tc_excess),
            adjustment=float(talent_risk_adj),
            interpretation=self._interpret_tc(tc)
        )
        
        # STEP 6: Calculate final V^R
        base_score = mean_score
        after_cv = base_score * cv_penalty
        final_vr = after_cv * talent_risk_adj
        
        # Clamp to [0, 100]
        final_vr = clamp(final_vr, Decimal("0"), Decimal("100"))
        
        # Calculate penalty amounts for reporting
        cv_penalty_amount = base_score - after_cv
        tc_penalty_amount = after_cv - final_vr
        
        logger.info(
            "vr_calculation_completed",
            vr_score=float(final_vr),
            base_score=float(base_score),
            cv_penalty_amount=float(cv_penalty_amount),
            tc_penalty_amount=float(tc_penalty_amount)
        )
        
        # Build result
        result = VRResult(
            vr_score=final_vr,
            weighted_mean=mean_score,
            cv=cv,
            cv_penalty=cv_penalty,
            talent_concentration=tc,
            talent_risk_adj=talent_risk_adj,
            sector=sector,
            dimension_scores={
                k: v for k, v in zip(self.DEFAULT_WEIGHTS.keys(), dimension_values)
            },
            dimension_weights=weights,
            base_score=base_score,
            cv_penalty_amount=cv_penalty_amount,
            tc_penalty_amount=tc_penalty_amount
        )
        
        logger.info("vr_result_summary", summary=result.get_summary())
        
        return result
    
    def _get_sector_weights(self, sector: str) -> Dict[str, Decimal]:
        """
        Get dimension weights for a sector.
        
        Handles various sector name formats from database.
        
        Args:
            sector: Sector name from database
        
        Returns:
            Dict of dimension weights (sum = 1.0)
        
        Raises:
            ValueError: If sector cannot be mapped
        """
       
        sector_mapping = {
            # Database name → VRCalculator key
            "financial": "financial_services",
            "financials": "financial_services",
            "financial services": "financial_services",
            "financial_services": "financial_services",
            
            "manufacturing": "manufacturing",
            "industrials": "manufacturing",
            
            "healthcare": "healthcare",
            "healthcare services": "healthcare",
            
            "retail": "retail",
            "consumer": "retail",
            
            "technology": "technology",
            "tech": "technology",
            
            "services": "business_services",
            "business services": "business_services",
            "business_services": "business_services",
        }
        
        sector_lower = sector.lower().strip()
        
        # Try direct lookup first
        if sector_lower in self.SECTOR_WEIGHTS:
            mapped_sector = sector_lower
        elif sector_lower in sector_mapping:
            # Use mapping
            mapped_sector = sector_mapping[sector_lower]
        else:
            # Not found - use default weights
            logger.warning(
                "unknown_sector_using_default",
                sector=sector,
                available=list(self.SECTOR_WEIGHTS.keys())
            )
            # Return default weights instead of failing
            return self.DEFAULT_WEIGHTS
        
        weights = self.SECTOR_WEIGHTS[mapped_sector]
        
        logger.debug(
            "sector_weights_selected",
            sector_from_db=sector,
            sector_used=mapped_sector,
            weights={k: float(v) for k, v in weights.items()}
        )
        
        return weights
    
    def _interpret_cv(self, cv: Decimal) -> str:
        """Interpret CV value for logging"""
        if cv < Decimal("0.2"):
            return "balanced"
        elif cv < Decimal("0.5"):
            return "moderate_imbalance"
        else:
            return "high_imbalance"
    
    def _interpret_tc(self, tc: Decimal) -> str:
        """Interpret TC value for logging"""
        if tc < Decimal("0.25"):
            return "distributed_low_risk"
        elif tc < Decimal("0.50"):
            return "moderate_concentration"
        else:
            return "high_concentration_high_risk"
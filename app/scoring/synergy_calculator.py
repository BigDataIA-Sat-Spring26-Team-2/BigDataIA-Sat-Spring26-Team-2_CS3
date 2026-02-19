from decimal import Decimal
from typing import NamedTuple
import structlog

from app.scoring.utils import to_decimal, clamp

logger = structlog.get_logger()


class SynergyResult(NamedTuple):
    """Result of synergy calculation with audit trail"""
    synergy_score: Decimal  # Final synergy score (0-100)
    vr_score: Decimal  # Input V^R
    hr_score: Decimal  # Input H^R
    base_synergy: Decimal  # V^R × H^R / 100
    alignment: Decimal  # Alignment factor (0-1)
    timing_factor: Decimal  # Market timing (0.8-1.2)
    
    def get_summary(self) -> dict:
        """Return summary dict for logging/API responses"""
        return {
            "synergy_score": float(self.synergy_score),
            "vr_score": float(self.vr_score),
            "hr_score": float(self.hr_score),
            "base_synergy": float(self.base_synergy),
            "alignment": float(self.alignment),
            "timing_factor": float(self.timing_factor)
        }


class SynergyCalculator:
    """
    Calculate synergy between V^R and H^R.
    
    Synergy represents the multiplicative benefit (or penalty) when company 
    capabilities and industry context are well-aligned (or misaligned).
    
    Formula:
        Synergy = (V^R × H^R / 100) × Alignment × TimingFactor
    
    Components:
        - Base synergy: Geometric mean scaled to [0, 100]
        - Alignment: How well V^R and H^R match (0 = opposite, 1 = perfect)
        - TimingFactor: Market/economic conditions (0.8 = recession, 1.2 = boom)
    
    Examples:
        - High V^R (80), High H^R (75), Good alignment (0.9):
          Synergy = (80 × 75 / 100) × 0.9 × 1.0 = 54.0
        
        - High V^R (80), Low H^R (40), Poor alignment (0.5):
          Synergy = (80 × 40 / 100) × 0.5 × 1.0 = 16.0
    """
    
    # TimingFactor bounds
    TIMING_MIN = Decimal("0.8")  # Economic downturn
    TIMING_MAX = Decimal("1.2")  # Economic boom
    TIMING_DEFAULT = Decimal("1.0")  # Normal conditions
    
    def calculate(
        self,
        vr_score: float,
        hr_score: float,
        alignment: float,
        timing_factor: float = 1.0,
    ) -> SynergyResult:
        """
        Calculate synergy score.
        
        Args:
            vr_score: Company V^R score (0-100)
            hr_score: Industry H^R score (0-100)
            alignment: Alignment factor (0-1)
                0.0 = Complete misalignment
                0.5 = Moderate alignment
                1.0 = Perfect alignment
            timing_factor: Market timing adjustment (0.8-1.2)
                0.8 = Recession (cautious AI adoption)
                1.0 = Normal conditions
                1.2 = Boom (aggressive AI investment)
        
        Returns:
            SynergyResult with complete calculation breakdown
        
        Raises:
            ValueError: If invalid inputs
    
        """
        logger.info(
            "synergy_calculation_started",
            vr_score=vr_score,
            hr_score=hr_score,
            alignment=alignment,
            timing_factor=timing_factor
        )
        
        # VALIDATION
        if not (0 <= vr_score <= 100):
            raise ValueError(f"V^R score must be in [0, 100], got {vr_score}")
        
        if not (0 <= hr_score <= 100):
            raise ValueError(f"H^R score must be in [0, 100], got {hr_score}")
        
        if not (0 <= alignment <= 1):
            raise ValueError(f"Alignment must be in [0, 1], got {alignment}")
        
        if not (0.8 <= timing_factor <= 1.2):
            raise ValueError(
                f"TimingFactor must be in [0.8, 1.2], got {timing_factor}"
            )
        
        # Convert to Decimal
        vr = to_decimal(vr_score, places=2)
        hr = to_decimal(hr_score, places=2)
        align = to_decimal(alignment, places=4)
        timing = to_decimal(timing_factor, places=2)
        
        # STEP 1: Calculate base synergy (geometric interaction)
        # V^R × H^R / 100
        # This normalizes the product back to [0, 100] range
        base_synergy = (vr * hr) / Decimal("100")
        
        # STEP 2: Apply alignment factor
        # Good alignment amplifies synergy, poor alignment dampens it
        aligned_synergy = base_synergy * align
        
        # STEP 3: Apply timing factor
        # Market conditions can boost or dampen synergy realization
        final_synergy = aligned_synergy * timing
        
        # STEP 4: Clamp to [0, 100] range
        synergy_bounded = clamp(final_synergy, min_val=Decimal("0"), max_val=Decimal("100"))
        
        logger.info(
            "synergy_calculation_completed",
            base_synergy=float(base_synergy),
            after_alignment=float(aligned_synergy),
            final_synergy=float(synergy_bounded)
        )
        
        # Build result
        result = SynergyResult(
            synergy_score=synergy_bounded,
            vr_score=vr,
            hr_score=hr,
            base_synergy=base_synergy,
            alignment=align,
            timing_factor=timing
        )
        
        logger.info("synergy_result_summary", summary=result.get_summary())
        
        return result
    
    def calculate_alignment(
        self,
        vr_score: float,
        hr_score: float,
    ) -> float:
        """
        Calculate alignment factor based on V^R and H^R similarity.
        
        Alignment measures how well company readiness matches industry context.
        Uses inverse of normalized difference: closer scores = higher alignment.
        
        Formula:
            diff = |V^R - H^R| / 100
            alignment = 1 - diff
        
        Args:
            vr_score: Company V^R score (0-100)
            hr_score: Industry H^R score (0-100)
        
        Returns:
            Alignment factor in [0, 1]
    
        """
        # Calculate normalized difference
        diff = abs(vr_score - hr_score) / 100.0
        
        # Alignment is inverse of difference
        alignment = 1.0 - diff
        
        return max(0.0, min(1.0, alignment))

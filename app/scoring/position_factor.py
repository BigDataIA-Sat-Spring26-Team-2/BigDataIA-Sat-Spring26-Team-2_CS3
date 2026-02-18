from decimal import Decimal
from typing import Dict
import structlog

from app.scoring.utils import to_decimal, clamp

logger = structlog.get_logger()


class PositionFactorCalculator:

    SECTOR_AVG_VR: Dict[str, float] = {
        "technology": 65.0,
        "financial_services": 55.0,
        "healthcare": 52.0,
        "business_services": 50.0,
        "retail": 48.0,
        "manufacturing": 45.0,
    }
    
    # Weights for components
    VR_WEIGHT = Decimal("0.6")
    MCAP_WEIGHT = Decimal("0.4")
    
    def calculate_position_factor(
        self,
        vr_score: float,
        sector: str,
        market_cap_percentile: float,
    ) -> Decimal:
        
        logger.info(
            "position_factor_calculation_started",
            vr_score=vr_score,
            sector=sector,
            market_cap_percentile=market_cap_percentile
        )
        
        if not (0 <= vr_score <= 100):
            raise ValueError(f"V^R score must be in [0, 100], got {vr_score}")
        
        if not (0 <= market_cap_percentile <= 1):
            raise ValueError(
                f"Market cap percentile must be in [0, 1], got {market_cap_percentile}"
            )
        
        sector_lower = sector.lower().strip()
        
        # STEP 1: Get sector average V^R
        sector_avg = self.SECTOR_AVG_VR.get(sector_lower, 50.0)
        
        if sector_lower not in self.SECTOR_AVG_VR:
            logger.warning(
                "unknown_sector_using_default",
                sector=sector,
                default_avg=50.0,
                available_sectors=list(self.SECTOR_AVG_VR.keys())
            )
        
        # STEP 2: Calculate V^R component
        vr_diff = vr_score - sector_avg
        vr_component_raw = vr_diff / 50.0
        
        vr_component = to_decimal(vr_component_raw, places=4)
        vr_component = clamp(vr_component, min_val=Decimal("-1"), max_val=Decimal("1"))
        
        # STEP 3: Calculate market cap component
        # Transform percentile [0, 1] to component [-1, 1]
        # 0.0 (smallest) → -1.0
        # 0.5 (median) → 0.0
        # 1.0 (largest) → +1.0
        mcap_component_raw = (market_cap_percentile - 0.5) * 2.0
        mcap_component = to_decimal(mcap_component_raw, places=4)
        
        # STEP 4: Weighted combination
        pf = (
            self.VR_WEIGHT * vr_component +
            self.MCAP_WEIGHT * mcap_component
        )
        
        # STEP 5: Final bounds check using utils.clamp
        pf_final = clamp(pf, min_val=Decimal("-1"), max_val=Decimal("1"))
        
        logger.info(
            "position_factor_calculated",
            vr_score=vr_score,
            sector_avg=sector_avg,
            vr_diff=vr_diff,
            vr_component=float(vr_component),
            mcap_percentile=market_cap_percentile,
            mcap_component=float(mcap_component),
            position_factor=float(pf_final)
        )
        
        return pf_final
    
    def get_sector_average(self, sector: str) -> float:
        sector_lower = sector.lower().strip()
        return self.SECTOR_AVG_VR.get(sector_lower, 50.0)


# if __name__ == "__main__":
#     calc = PositionFactorCalculator()
    
#     print("=" * 70)
#     print("POSITION FACTOR CALCULATOR - EXAMPLES")
#     print("=" * 70)
    
#     test_cases = [
#         {
#             "name": "NVIDIA",
#             "vr": 90.0,
#             "sector": "technology",
#             "mcap_pct": 0.95,
#             "expected_pf": 0.9,
#             "reason": "AI chip leader"
#         },
#         {
#             "name": "JPMorgan",
#             "vr": 70.0,
#             "sector": "financial_services",
#             "mcap_pct": 0.85,
#             "expected_pf": 0.5,
#             "reason": "$15B+ tech spend"
#         },
#         {
#             "name": "Walmart",
#             "vr": 60.0,
#             "sector": "retail",
#             "mcap_pct": 0.75,
#             "expected_pf": 0.3,
#             "reason": "Supply chain AI"
#         },
#         {
#             "name": "General Electric",
#             "vr": 50.0,
#             "sector": "manufacturing",
#             "mcap_pct": 0.50,
#             "expected_pf": 0.0,
#             "reason": "Industrial IoT"
#         },
#         {
#             "name": "Dollar General",
#             "vr": 40.0,
#             "sector": "retail",
#             "mcap_pct": 0.30,
#             "expected_pf": -0.3,
#             "reason": "Limited tech"
#         }
#     ]
    
#     for case in test_cases:
#         print(f"\n{case['name']} ({case['reason']})")
#         print(f"  Sector: {case['sector']}")
#         print(f"  V^R: {case['vr']}/100")
#         print(f"  Market Cap Percentile: {case['mcap_pct']*100:.0f}th")
        
#         pf = calc.calculate_position_factor(
#             vr_score=case['vr'],
#             sector=case['sector'],
#             market_cap_percentile=case['mcap_pct']
#         )
        
#         print(f"  → Position Factor: {pf:+.2f}")
#         print(f"     Expected: {case['expected_pf']:+.1f}")
#         print(f"     Match: {'✓' if abs(float(pf) - case['expected_pf']) < 0.15 else '✗'}")
    
#     print("\n" + "=" * 70)
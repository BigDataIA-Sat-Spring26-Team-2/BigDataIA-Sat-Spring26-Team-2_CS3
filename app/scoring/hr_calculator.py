"""
H^R (Industry AI-Readiness) Calculator.

Calculates industry-level AI readiness adjusted for company position within sector.

Formula:
    H^R = H^R_base × (1 + δ × PF)

Where:
    - H^R_base: Industry baseline from database (industries table)
    - δ = 0.15: Position adjustment coefficient
    - PF: Position Factor ∈ [-1, 1]
"""

from decimal import Decimal
from typing import NamedTuple, Optional, Dict
import structlog

from app.scoring.utils import to_decimal, clamp  # ✅ Use utils
from app.services.snowflake import get_connection
from app.config import get_settings

logger = structlog.get_logger()


class HRResult(NamedTuple):
    """Result of H^R calculation with audit trail"""
    hr_score: Decimal
    hr_base: Decimal
    position_factor: Decimal
    position_adjustment: Decimal
    sector: str
    
    def get_summary(self) -> dict:
        return {
            "hr_score": float(self.hr_score),
            "hr_base": float(self.hr_base),
            "position_factor": float(self.position_factor),
            "position_adjustment": float(self.position_adjustment),
            "sector": self.sector
        }


class HRCalculator:
    # Position adjustment coefficient (CORRECTED in v3.0)
    DELTA = Decimal("0.15")
    
    FALLBACK_HR_BASE: Dict[str, float] = {
        "technology": 75.0,
        "financial_services": 65.0,
        "financial": 65.0,
        "healthcare": 55.0,
        "retail": 50.0,
        "business_services": 48.0,
        "professional_services": 48.0,
        "manufacturing": 45.0,
        "energy": 40.0,
    }
    
    def __init__(self):
        self.settings = get_settings()
        self._hr_base_cache: Dict[str, float] = {}  # Cache for performance
    
    def get_hr_base_from_db(self, industry_id: str) -> Optional[float]:

        conn = None
        cur = None
        
        try:
            conn = get_connection()
            cur = conn.cursor()
            
            sql = f"""
                SELECT h_r_base, name
                FROM {self.settings.SNOWFLAKE_DATABASE}.{self.settings.SNOWFLAKE_SCHEMA}.industries
                WHERE id = %s
            """
            
            cur.execute(sql, (str(industry_id),))
            row = cur.fetchone()
            
            if row and row[0] is not None:
                h_r_base = float(row[0])
                industry_name = row[1]
                
                # Cache it
                self._hr_base_cache[industry_id] = h_r_base
                
                logger.info(
                    "hr_base_from_db",
                    industry_id=industry_id,
                    industry_name=industry_name,
                    h_r_base=h_r_base
                )
                return h_r_base
            
            logger.warning("hr_base_not_found_in_db", industry_id=industry_id)
            return None
            
        except Exception as e:
            logger.error("hr_base_db_error", industry_id=industry_id, error=str(e))
            return None
        
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
    
    def get_hr_base_by_sector(self, sector: str) -> Optional[float]:
        # Check cache first
        cache_key = f"sector:{sector.lower()}"
        if cache_key in self._hr_base_cache:
            return self._hr_base_cache[cache_key]
        
        conn = None
        cur = None
        
        try:
            conn = get_connection()
            cur = conn.cursor()
            
            sql = f"""
                SELECT h_r_base, name
                FROM {self.settings.SNOWFLAKE_DATABASE}.{self.settings.SNOWFLAKE_SCHEMA}.industries
                WHERE LOWER(sector) = LOWER(%s)
                LIMIT 1
            """
            
            cur.execute(sql, (sector,))
            row = cur.fetchone()
            
            if row and row[0] is not None:
                h_r_base = float(row[0])
                industry_name = row[1]
                
                # Cache it
                self._hr_base_cache[cache_key] = h_r_base
                
                logger.info(
                    "hr_base_from_db_by_sector",
                    sector=sector,
                    industry_name=industry_name,
                    h_r_base=h_r_base
                )
                return h_r_base
            
            logger.warning("hr_base_not_found_by_sector", sector=sector)
            return None
            
        except Exception as e:
            logger.error("hr_base_db_error", sector=sector, error=str(e))
            return None
        
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
    
    def calculate(
        self,
        sector: str,
        position_factor: float,
        hr_base: float = None,
        industry_id: str = None,
    ) -> HRResult:

        logger.info(
            "hr_calculation_started",
            sector=sector,
            position_factor=position_factor,
            hr_base_override=hr_base,
            industry_id=industry_id
        )
        
        if not (-1.0 <= position_factor <= 1.0):
            raise ValueError(
                f"Position factor must be in [-1, 1], got {position_factor}"
            )
        
        sector_lower = sector.lower().strip()
        
        # STEP 1: Determine H^R base (priority order)
        base_source = "unknown"
        
        if hr_base is not None:
            base_float = hr_base
            base_source = "explicit_override"
            logger.info("using_hr_base_override", hr_base=hr_base)
            
        elif industry_id is not None:
            db_base = self.get_hr_base_from_db(industry_id)
            if db_base is not None:
                base_float = db_base
                base_source = "database_by_id"
                logger.info("using_hr_base_from_db_by_id", hr_base=db_base)
            else:
                db_base = self.get_hr_base_by_sector(sector)
                if db_base is not None:
                    base_float = db_base
                    base_source = "database_by_sector"
                else:
                    base_float = self.FALLBACK_HR_BASE.get(sector_lower, 50.0)
                    base_source = "fallback_constant"
                    logger.warning(
                        "using_hr_base_fallback",
                        sector=sector,
                        hr_base=base_float
                    )
        else:
            db_base = self.get_hr_base_by_sector(sector)
            if db_base is not None:
                base_float = db_base
                base_source = "database_by_sector"
                logger.info("using_hr_base_from_db_by_sector", hr_base=db_base)
            else:
                base_float = self.FALLBACK_HR_BASE.get(sector_lower, 50.0)
                base_source = "fallback_constant"
                logger.warning(
                    "using_hr_base_fallback",
                    sector=sector,
                    hr_base=base_float
                )
        
        # Convert to Decimal using utils
        base = to_decimal(base_float, places=2) 
        
        # Validate H^R base
        if not (0 <= base <= 100):
            raise ValueError(f"H^R base must be in [0, 100], got {base}")
        
        # STEP 2: Convert position factor to Decimal using utils
        pf = to_decimal(position_factor, places=4)
        
        # STEP 3: Calculate position adjustment multiplier
        # Adjustment = 1 + δ × PF
        position_adjustment = Decimal("1") + self.DELTA * pf
        
        # STEP 4: Calculate H^R
        hr_raw = base * position_adjustment
        
        # STEP 5: Clamp to [0, 100] using utils
        hr_final = clamp(hr_raw, min_val=Decimal("0"), max_val=Decimal("100"))  # ✅ Use utils
        
        logger.info(
            "hr_calculation_completed",
            hr_base=float(base),
            hr_base_source=base_source,
            position_factor=float(pf),
            position_adjustment=float(position_adjustment),
            hr_score=float(hr_final)
        )
        
        # Build result
        result = HRResult(
            hr_score=hr_final,
            hr_base=base,
            position_factor=pf,
            position_adjustment=position_adjustment,
            sector=sector
        )
        
        logger.info("hr_result_summary", summary=result.get_summary())
        
        return result
    
    def get_industry_baseline(self, sector: str) -> float:
 
        db_base = self.get_hr_base_by_sector(sector)
        if db_base is not None:
            return db_base
        
        sector_lower = sector.lower().strip()
        return self.FALLBACK_HR_BASE.get(sector_lower, 50.0)

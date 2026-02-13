from typing import Dict, List, Tuple
from decimal import Decimal
from uuid import UUID
import re
import structlog

from app.services.snowflake import get_connection
from app.config import get_settings

logger = structlog.get_logger(__name__)


class SECItem1Analyzer:
    """
    Analyze SEC Item 1 (Business section) for AI use case evidence.
    
    Scoring criteria:
    - Production AI mentions: +30 points
    - ROI/revenue mentions: +25 points
    - Use case count: +25 points
    - Product diversity: +20 points
    """
    
    PRODUCTION_KEYWORDS = [
        "production ai", "deployed model", "ai in production",
        "live ai", "production deployment", "ai-powered product",
        "ai-enabled", "machine learning in production"
    ]
    
    ROI_KEYWORDS = [
        "roi", "return on investment", "cost savings",
        "revenue from ai", "measurable impact", "efficiency gains",
        "productivity increase", "ai revenue"
    ]
    
    USE_CASE_KEYWORDS = [
        "use case", "application", "ai solution",
        "recommendation system", "fraud detection", "predictive",
        "personalization", "automation", "optimization"
    ]
    
    PRODUCT_KEYWORDS = [
        "ai product", "ml product", "intelligent",
        "smart", "automated", "predictive analytics"
    ]
    
    def analyze_business_section(
        self,
        company_id: UUID,
        ticker: str
    ) -> Tuple[Decimal, Decimal, Dict]:
        """
        Analyze Item 1 Business section for use case evidence.
        
        Returns:
            (score, confidence, metadata)
        """
        logger.info("sec_item_1_analysis_started", ticker=ticker)
        
        # Fetch Item 1 chunks from Snowflake
        text = self._fetch_item_1_text(company_id, ticker)
        
        if not text:
            logger.warning("no_item_1_data", ticker=ticker)
            return (Decimal("0.0"), Decimal("0.5"), {"reason": "no_data"})
        
        # Score components
        production_score = self._score_production_mentions(text)
        roi_score = self._score_roi_mentions(text)
        use_case_score = self._score_use_case_count(text)
        product_score = self._score_product_diversity(text)
        
        # Weighted combination
        total_score = (
            production_score * Decimal("0.30") +
            roi_score * Decimal("0.25") +
            use_case_score * Decimal("0.25") +
            product_score * Decimal("0.20")
        )
        
        # Calculate confidence based on text length
        word_count = len(text.split())
        confidence = min(Decimal("0.5") + Decimal(word_count) / 10000, Decimal("0.95"))
        
        metadata = {
            "production_score": float(production_score),
            "roi_score": float(roi_score),
            "use_case_score": float(use_case_score),
            "product_score": float(product_score),
            "word_count": word_count,
            "section": "Item 1 - Business"
        }
        
        logger.info(
            "sec_item_1_scored",
            ticker=ticker,
            total_score=float(total_score),
            metadata=metadata
        )
        
        return (total_score, confidence, metadata)
    
    def _fetch_item_1_text(self, company_id: UUID, ticker: str) -> str:
        """Fetch Item 1 Business section chunks"""
        settings = get_settings()
        conn = get_connection()
        cur = conn.cursor()
        
        try:
            cur.execute(f"""
                SELECT dc.chunk_text
                FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.document_chunks dc
                JOIN {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.documents d
                  ON dc.document_id = d.id
                WHERE d.company_id = %s
                  AND dc.section = 'item_1_business'
                ORDER BY d.filing_date DESC, dc.chunk_index
            """, (str(company_id),))
            
            rows = cur.fetchall()
            
            if not rows:
                logger.debug("no_item_1_chunks", ticker=ticker)
                return ""
            
            # Combine chunks
            text = " ".join(row[0] for row in rows if row[0])
            logger.debug("item_1_fetched", ticker=ticker, chunks=len(rows), words=len(text.split()))
            
            return text
            
        finally:
            cur.close()
            conn.close()
    
    def _score_production_mentions(self, text: str) -> Decimal:
        """Score production AI mentions (0-100)"""
        text_lower = text.lower()
        
        matches = sum(1 for kw in self.PRODUCTION_KEYWORDS if kw in text_lower)
        
        # 0 matches = 0, 1 match = 40, 2 matches = 70, 3+ = 100
        if matches == 0:
            return Decimal("0")
        elif matches == 1:
            return Decimal("40")
        elif matches == 2:
            return Decimal("70")
        else:
            return Decimal("100")
    
    def _score_roi_mentions(self, text: str) -> Decimal:
        """Score ROI/revenue mentions (0-100)"""
        text_lower = text.lower()
        
        matches = sum(1 for kw in self.ROI_KEYWORDS if kw in text_lower)
        
        # 0 = 0, 1-2 = 50, 3+ = 100
        if matches == 0:
            return Decimal("0")
        elif matches <= 2:
            return Decimal("50")
        else:
            return Decimal("100")
    
    def _score_use_case_count(self, text: str) -> Decimal:
        """Score use case mentions (0-100)"""
        text_lower = text.lower()
        
        matches = sum(1 for kw in self.USE_CASE_KEYWORDS if kw in text_lower)
        
        # Linear scaling: 0 = 0, 5 matches = 100
        score = min(100, matches * 20)
        return Decimal(str(score))
    
    def _score_product_diversity(self, text: str) -> Decimal:
        """Score AI product diversity (0-100)"""
        text_lower = text.lower()
        
        matches = sum(1 for kw in self.PRODUCT_KEYWORDS if kw in text_lower)
        
        # 0 = 0, 3+ = 100
        score = min(100, matches * 33)
        return Decimal(str(score))
class SECItem1AAnalyzer:
    """
    Analyze SEC Item 1A (Risk Factors) for AI governance evidence.
    
    Scoring criteria:
    - AI/ML risk mentions: +30 points
    - Cybersecurity/data privacy: +25 points  
    - Technology obsolescence risks: +25 points
    - Regulatory compliance: +20 points
    """
    
    AI_RISK_KEYWORDS = [
        "artificial intelligence risk", "machine learning risk",
        "ai model risk", "algorithmic bias", "ai ethics",
        "model accuracy", "ai liability", "automated decision"
    ]
    
    CYBER_DATA_KEYWORDS = [
        "cybersecurity", "data privacy", "data breach",
        "gdpr", "ccpa", "data protection", "information security",
        "cyber attack", "data governance"
    ]
    
    TECH_OBSOLESCENCE_KEYWORDS = [
        "technology obsolescence", "legacy systems",
        "technological change", "rapidly evolving technology",
        "technology investment", "infrastructure modernization"
    ]
    
    REGULATORY_KEYWORDS = [
        "ai regulation", "regulatory compliance",
        "technology regulation", "data regulation",
        "compliance framework", "regulatory risk"
    ]
    
    def analyze_risk_section(
        self,
        company_id: UUID,
        ticker: str
    ) -> Tuple[Decimal, Decimal, Dict]:
        """Analyze Item 1A for governance evidence."""
        
        text = self._fetch_item_1a_text(company_id, ticker)
        
        if not text:
            return (Decimal("0.0"), Decimal("0.5"), {"reason": "no_data"})
        
        ai_risk_score = self._score_ai_risks(text)
        cyber_score = self._score_cyber_data(text)
        tech_obs_score = self._score_tech_obsolescence(text)
        regulatory_score = self._score_regulatory(text)
        
        total_score = (
            ai_risk_score * Decimal("0.30") +
            cyber_score * Decimal("0.25") +
            tech_obs_score * Decimal("0.25") +
            regulatory_score * Decimal("0.20")
        )
        
        word_count = len(text.split())
        confidence = min(Decimal("0.5") + Decimal(word_count) / 10000, Decimal("0.95"))
        
        metadata = {
            "ai_risk_score": float(ai_risk_score),
            "cyber_score": float(cyber_score),
            "tech_obsolescence_score": float(tech_obs_score),
            "regulatory_score": float(regulatory_score),
            "word_count": word_count,
            "section": "Item 1A - Risk Factors"
        }
        
        return (total_score, confidence, metadata)
    
    def _fetch_item_1a_text(self, company_id: UUID, ticker: str) -> str:
        """Fetch Item 1A chunks"""
        settings = get_settings()
        conn = get_connection()
        cur = conn.cursor()
        
        try:
            cur.execute(f"""
                SELECT dc.chunk_text
                FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.document_chunks dc
                JOIN {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.documents d
                  ON dc.document_id = d.id
                WHERE d.company_id = %s
                  AND dc.section = 'item_1a_risk_factors'
                ORDER BY d.filing_date DESC, dc.chunk_index
            """, (str(company_id),))
            
            rows = cur.fetchall()
            return " ".join(row[0] for row in rows if row[0])
            
        finally:
            cur.close()
            conn.close()
    
    def _score_ai_risks(self, text: str) -> Decimal:
        """Score AI/ML risk mentions (0-100)"""
        matches = sum(1 for kw in self.AI_RISK_KEYWORDS if kw in text.lower())
        return Decimal(str(min(100, matches * 25)))
    
    def _score_cyber_data(self, text: str) -> Decimal:
        """Score cyber/data privacy mentions (0-100)"""
        matches = sum(1 for kw in self.CYBER_DATA_KEYWORDS if kw in text.lower())
        return Decimal(str(min(100, matches * 15)))
    
    def _score_tech_obsolescence(self, text: str) -> Decimal:
        """Score technology obsolescence mentions (0-100)"""
        matches = sum(1 for kw in self.TECH_OBSOLESCENCE_KEYWORDS if kw in text.lower())
        return Decimal(str(min(100, matches * 20)))
    
    def _score_regulatory(self, text: str) -> Decimal:
        """Score regulatory compliance mentions (0-100)"""
        matches = sum(1 for kw in self.REGULATORY_KEYWORDS if kw in text.lower())
        return Decimal(str(min(100, matches * 25)))
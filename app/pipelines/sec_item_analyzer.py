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
        "ai-enabled", "machine learning in production",
        "production system", "deployed ai", "operational ai",
    "live model", "production ml", "ai-driven product",
    "production algorithm", "deployed solution", "live deployment",
    "production ready", "scaled deployment", "enterprise deployment",
    "customer-facing ai", "production workload", "ai at scale"
    ]
    
    ROI_KEYWORDS = [
        "roi", "return on investment", "cost savings",
        "revenue from ai", "measurable impact", "efficiency gains",
        "productivity increase", "ai revenue",
        "cost reduction", "revenue growth", "margin improvement",
    "operational efficiency", "labor savings", "time savings",
    "improved productivity", "increased revenue", "reduced costs",
    "financial benefit", "business value", "quantifiable benefit",
    "payback period", "net benefit", "positive return",
    "cost avoidance", "profit improvement", "performance improvement"
    ]
    
    USE_CASE_KEYWORDS = [
        "use case", "application", "ai solution",
        "recommendation system", "fraud detection", "predictive",
        "personalization", "automation", "optimization",
        "customer service", "chatbot", "virtual assistant",
    "demand forecasting", "inventory optimization", "supply chain",
    "risk assessment", "credit scoring", "underwriting",
    "predictive maintenance", "quality control", "anomaly detection",
    "natural language processing", "image recognition", "computer vision",
    "sentiment analysis", "customer segmentation", "churn prediction",
    "dynamic pricing", "recommendation engine", "search optimization"
    ]
    
    PRODUCT_KEYWORDS = [
        "ai product", "ml product", "intelligent",
        "smart", "automated", "predictive analytics",
         "ai-powered", "ai-driven", "ai-based", "ml-based",
    "cognitive", "intelligent system", "smart system",
    "adaptive", "self-learning", "data-driven product",
    "analytics platform", "ai platform", "ml platform",
    "intelligent application", "smart technology"
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
        
        
        text = self._fetch_item_1_text(company_id, ticker)
        
        if not text:
            logger.warning("no_item_1_data", ticker=ticker)
            return (Decimal("0.0"), Decimal("0.5"), {"reason": "no_data"})
        
       
        production_score, production_kws = self._score_production_mentions(text)
        roi_score, roi_kws = self._score_roi_mentions(text)
        use_case_score, use_case_kws = self._score_use_case_count(text)
        product_score, product_kws = self._score_product_diversity(text)
        
        
        total_score = (
            production_score * Decimal("0.30") +
            roi_score * Decimal("0.25") +
            use_case_score * Decimal("0.25") +
            product_score * Decimal("0.20")
        )
        
        
        word_count = len(text.split())
        confidence = min(Decimal("0.5") + Decimal(word_count) / 10000, Decimal("0.95"))
        
        metadata = {
            "production_score": float(production_score),
            "roi_score": float(roi_score),
            "use_case_score": float(use_case_score),
            "product_score": float(product_score),
            "word_count": word_count,
            "section": "Item 1 - Business",
    
    
    "keywords_matched": {
        "production": production_kws,
        "roi": roi_kws,
        "use_case": use_case_kws,
        "product": product_kws,
    },
    
    
    "keyword_counts": {
        "production": len(production_kws),
        "roi": len(roi_kws),
        "use_case": len(use_case_kws),
        "product": len(product_kws),
    },
    
    
    "total_keywords_found": len(set(production_kws + roi_kws + use_case_kws + product_kws))
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
            
            
            text = " ".join(row[0] for row in rows if row[0])
            logger.debug("item_1_fetched", ticker=ticker, chunks=len(rows), words=len(text.split()))
            
            return text
            
        finally:
            cur.close()
            conn.close()
    
    def _score_production_mentions(self, text: str) -> Tuple[Decimal, List[str]]:
        """Score production AI mentions - RETURNS (score, matched_keywords)"""
        text_lower = text.lower()
    
   
        matched_keywords = [kw for kw in self.PRODUCTION_KEYWORDS if kw in text_lower]
        matches = len(matched_keywords)
    
    
        if matches == 0:
            score = Decimal("0")
        elif matches == 1:
            score = Decimal("40")
        elif matches == 2:
            score = Decimal("70")
        else:
            score = Decimal("100")
    
        return (score, matched_keywords)
    
    def _score_roi_mentions(self, text: str) -> Tuple[Decimal, List[str]]:
        """Score ROI/revenue mentions (0-100)"""
        text_lower = text.lower()
    
        matched_keywords = [kw for kw in self.ROI_KEYWORDS if kw in text_lower]
        matches = len(matched_keywords)
    
        if matches == 0:
            score = Decimal("0")
        elif matches <= 2:
            score = Decimal("50")
        else:
            score = Decimal("100")
    
        return (score, matched_keywords)
    
    def _score_use_case_count(self, text: str) -> Tuple[Decimal, List[str]]:
        """Score use case mentions - RETURNS (score, matched_keywords)"""
        text_lower = text.lower()
    
        matched_keywords = [kw for kw in self.USE_CASE_KEYWORDS if kw in text_lower]
        matches = len(matched_keywords)
    
        score = min(100, matches * 20)
        return (Decimal(str(score)), matched_keywords)
    
    def _score_product_diversity(self, text: str) -> Tuple[Decimal, List[str]]:
        """Score product diversity - RETURNS (score, matched_keywords)"""
        text_lower = text.lower()
    
        matched_keywords = [kw for kw in self.PRODUCT_KEYWORDS if kw in text_lower]
        matches = len(matched_keywords)
    
        score = min(100, matches * 33)
        return (Decimal(str(score)), matched_keywords)
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
        "model accuracy", "ai liability", "automated decision",
        "ai fairness", "model bias", "discriminatory algorithm",
    "ai explainability", "black box", "model interpretability",
    "ai safety", "adversarial attack", "model robustness",
    "ai hallucination", "model drift", "data quality risk",
    "training data bias", "ai governance risk", "responsible ai"
    ]
    
    CYBER_DATA_KEYWORDS = [
        "cybersecurity", "data privacy", "data breach",
        "gdpr", "ccpa", "data protection", "information security",
        "cyber attack", "data governance",
        "ransomware", "phishing", "malware", "hacking",
    "data encryption", "access control", "authentication",
    "hipaa", "pci dss", "sox compliance", "privacy law",
    "personal data", "sensitive data", "pii", "phi",
    "security incident", "vulnerability", "penetration testing",
    "security audit", "iso 27001", "nist framework"
    ]
    
    TECH_OBSOLESCENCE_KEYWORDS = [
        "technology obsolescence", "legacy systems",
        "technological change", "rapidly evolving technology",
        "technology investment", "infrastructure modernization",
         "outdated technology", "aging infrastructure", "end of life",
    "technical debt", "system upgrade", "platform migration",
    "cloud migration", "digital transformation",
    "technology refresh", "infrastructure renewal",
    "legacy application", "system replacement", "modernization initiative"
    ]
    
    REGULATORY_KEYWORDS = [
        "ai regulation", "regulatory compliance",
        "technology regulation", "data regulation",
        "compliance framework", "regulatory risk",
        "regulatory requirement", "compliance obligation",
    "regulatory change", "new regulation", "proposed regulation",
    "regulatory scrutiny", "regulatory enforcement",
    "compliance monitoring", "regulatory reporting",
    "audit requirement", "regulatory standard",
    "eu ai act", "algorithmic accountability"
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
        
        
        ai_risk_score, ai_risk_kws = self._score_ai_risks(text)
        cyber_score, cyber_kws = self._score_cyber_data(text)
        tech_obs_score, tech_obs_kws = self._score_tech_obsolescence(text)
        regulatory_score, reg_kws = self._score_regulatory(text)
        
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
            "section": "Item 1A - Risk Factors",
    
    
            "keywords_matched": {
            "ai_risk": ai_risk_kws,
            "cyber_data": cyber_kws,
            "tech_obsolescence": tech_obs_kws,
            "regulatory": reg_kws,
            },
    
    
            "keyword_counts": {
            "ai_risk": len(ai_risk_kws),
            "cyber_data": len(cyber_kws),
            "tech_obsolescence": len(tech_obs_kws),
            "regulatory": len(reg_kws),
        },
    
    
    "total_keywords_found": len(set(ai_risk_kws + cyber_kws + tech_obs_kws + reg_kws))
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
    
    def _score_ai_risks(self, text: str) -> Tuple[Decimal, List[str]]:
        """Score AI/ML risk mentions - RETURNS (score, matched_keywords)"""
        text_lower = text.lower()
    
        matched_keywords = [kw for kw in self.AI_RISK_KEYWORDS if kw in text_lower]
        matches = len(matched_keywords)
    
        score = min(100, matches * 25)
        return (Decimal(str(score)), matched_keywords)
    
    def _score_cyber_data(self, text: str) -> Tuple[Decimal, List[str]]:
        """Score cyber/data privacy mentions - RETURNS (score, matched_keywords)"""
        text_lower = text.lower()
    
        matched_keywords = [kw for kw in self.CYBER_DATA_KEYWORDS if kw in text_lower]
        matches = len(matched_keywords)
    
        score = min(100, matches * 15)
        return (Decimal(str(score)), matched_keywords)
    
    def _score_tech_obsolescence(self, text: str) -> Tuple[Decimal, List[str]]:
        """Score technology obsolescence mentions - RETURNS (score, matched_keywords)"""
        text_lower = text.lower()
    
        matched_keywords = [kw for kw in self.TECH_OBSOLESCENCE_KEYWORDS if kw in text_lower]
        matches = len(matched_keywords)
    
        score = min(100, matches * 20)
        return (Decimal(str(score)), matched_keywords)
    
    def _score_regulatory(self, text: str) -> Tuple[Decimal, List[str]]:
        """Score regulatory compliance mentions - RETURNS (score, matched_keywords)"""
        text_lower = text.lower()
    
        matched_keywords = [kw for kw in self.REGULATORY_KEYWORDS if kw in text_lower]
        matches = len(matched_keywords)
    
        score = min(100, matches * 25)
        return (Decimal(str(score)), matched_keywords)
class SECItem7Analyzer:
    """
    Analyze SEC Item 7 (MD&A) for leadership commitment evidence.
    
    Scoring criteria:
    - AI strategy discussion: +30 points
    - R&D/tech investment: +25 points
    - AI project updates: +25 points
    - Executive AI priorities: +20 points
    """
    
    STRATEGY_KEYWORDS = [
        "ai strategy", "artificial intelligence strategy",
        "digital transformation strategy", "technology roadmap",
        "ai initiative", "ml strategy", "data strategy",
        "innovation strategy", "technology priorities",
        "strategic ai", "ai transformation", "digital strategy",
    "technology vision", "innovation roadmap", "ai roadmap",
    "strategic technology", "digital first", "ai-first",
    "technology modernization", "digital innovation",
    "ai adoption", "technology strategy", "platform strategy"
    ]
    
    INVESTMENT_KEYWORDS = [
        "r&d investment", "technology investment",
        "ai investment", "capex technology", "technology spending",
        "research and development", "innovation investment",
        "digital investment", "technology budget",
        "technology capex", "it spending", "tech budget",
    "innovation spending", "digital capex", "cloud investment",
    "infrastructure investment", "platform investment",
    "r&d expenditure", "development cost", "innovation funding",
    "technology allocation", "it budget", "capital investment technology"
    ]
    
    PROJECT_KEYWORDS = [
        "ai project", "ml deployment", "ai implementation",
        "technology implementation", "digital project",
        "ai rollout", "pilot program", "proof of concept",
        "production deployment",
         "ai initiative", "ml initiative", "technology project",
    "digital initiative", "implementation plan", "rollout plan",
    "pilot deployment", "beta program", "technology launch",
    "platform launch", "system deployment", "go-live",
    "production release", "technology rollout"
    ]
    
    EXECUTIVE_PRIORITY_KEYWORDS = [
        "strategic priority", "executive focus",
        "management priority", "key initiative",
        "top priority", "strategic objective",
        "management believes", "our strategy",
           "focus area", "key focus", "strategic focus",
    "executive commitment", "leadership focus", "board priority",
    "ceo priority", "management focus", "strategic imperative",
    "critical priority", "core strategy", "strategic pillar",
    "key objective", "primary focus", "management objective"
    ]
    
    def analyze_mda_section(
        self,
        company_id: UUID,
        ticker: str
    ) -> Tuple[Decimal, Decimal, Dict]:
        """Analyze Item 7 MD&A for leadership signals."""
        
        logger.info("sec_item_7_analysis_started", ticker=ticker)
        
        text = self._fetch_item_7_text(company_id, ticker)
        
        if not text:
            logger.warning("no_item_7_data", ticker=ticker)
            return (Decimal("0.0"), Decimal("0.5"), {"reason": "no_data"})
        
        
        strategy_score, strategy_kws = self._score_strategy(text)
        investment_score, investment_kws = self._score_investment(text)
        project_score, project_kws = self._score_projects(text)
        priority_score, priority_kws = self._score_executive_priority(text)
        
        total_score = (
            strategy_score * Decimal("0.30") +
            investment_score * Decimal("0.25") +
            project_score * Decimal("0.25") +
            priority_score * Decimal("0.20")
        )
        
        word_count = len(text.split())
        confidence = min(Decimal("0.5") + Decimal(word_count) / 10000, Decimal("0.95"))
        
        metadata = {
            "strategy_score": float(strategy_score),
            "investment_score": float(investment_score),
            "project_score": float(project_score),
            "priority_score": float(priority_score),
            "word_count": word_count,
            "section": "Item 7 - MD&A",
    
    
            "keywords_matched": {
                "strategy": strategy_kws,
                "investment": investment_kws,
                "project": project_kws,
                "executive_priority": priority_kws,
            },
    
    
            "keyword_counts": {
                "strategy": len(strategy_kws),
                "investment": len(investment_kws),
                "project": len(project_kws),
                "executive_priority": len(priority_kws),
        },
    
    
    "total_keywords_found": len(set(strategy_kws + investment_kws + project_kws + priority_kws))
        }
        
        logger.info(
            "sec_item_7_scored",
            ticker=ticker,
            total_score=float(total_score),
            metadata=metadata
        )
        
        return (total_score, confidence, metadata)
    
    def _fetch_item_7_text(self, company_id: UUID, ticker: str) -> str:
        """Fetch Item 7 MD&A chunks"""
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
                  AND dc.section = 'item_7_mda'
                ORDER BY d.filing_date DESC, dc.chunk_index
            """, (str(company_id),))
            
            rows = cur.fetchall()
            
            if not rows:
                logger.debug("no_item_7_chunks", ticker=ticker)
                return ""
            
            text = " ".join(row[0] for row in rows if row[0])
            logger.debug("item_7_fetched", ticker=ticker, chunks=len(rows), words=len(text.split()))
            
            return text
            
        finally:
            cur.close()
            conn.close()
    
    def _score_strategy(self, text: str) -> Tuple[Decimal, List[str]]:
        """Score AI strategy discussion - RETURNS (score, matched_keywords)"""
        text_lower = text.lower()
    
        matched_keywords = [kw for kw in self.STRATEGY_KEYWORDS if kw in text_lower]
        matches = len(matched_keywords)
    
  
        if matches == 0:
            score = Decimal("0")
        elif matches == 1:
            score = Decimal("40")
        elif matches == 2:
            score = Decimal("70")
        else:
            score = Decimal("100")
    
        return (score, matched_keywords)
    
    def _score_investment(self, text: str) -> Tuple[Decimal, List[str]]:
        """Score technology investment mentions - RETURNS (score, matched_keywords)"""
        text_lower = text.lower()
    
        matched_keywords = [kw for kw in self.INVESTMENT_KEYWORDS if kw in text_lower]
        matches = len(matched_keywords)
    
        score = min(100, matches * 20)
        return (Decimal(str(score)), matched_keywords)
    
    def _score_projects(self, text: str) -> Tuple[Decimal, List[str]]:
        """Score AI project mentions - RETURNS (score, matched_keywords)"""
        text_lower = text.lower()
    
        matched_keywords = [kw for kw in self.PROJECT_KEYWORDS if kw in text_lower]
        matches = len(matched_keywords)
    
        score = min(100, matches * 15)
        return (Decimal(str(score)), matched_keywords)
    
    def _score_executive_priority(self, text: str) -> Tuple[Decimal, List[str]]:
        """Score executive priority mentions - RETURNS (score, matched_keywords)"""
        text_lower = text.lower()
    
        matched_keywords = [kw for kw in self.EXECUTIVE_PRIORITY_KEYWORDS if kw in text_lower]
        matches = len(matched_keywords)
    
        score = min(100, matches * 20)
        return (Decimal(str(score)), matched_keywords)


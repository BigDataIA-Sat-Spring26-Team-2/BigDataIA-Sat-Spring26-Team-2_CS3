from decimal import Decimal
from typing import Optional
from uuid import UUID
import re
from app.services.snowflake import get_connection
from app.config import get_settings
from app.models.board import GovernanceSignal


class BoardCompositionAnalyzer:
    
    AI_EXPERTISE_KEYWORDS = [
        "artificial intelligence", "machine learning", "deep learning",
        "neural network", "natural language processing", "nlp",
        "computer vision", "data science", "predictive analytics",
        "chief data officer", "cdo", "chief ai officer", "caio",
        "chief technology officer", "cto", "chief information officer", "cio",
        "chief digital officer", "chief analytics officer", "cao",
        "ai strategy", "ai transformation", "digital transformation",
        "technology strategy", "innovation strategy", "data strategy",
        "tech industry", "silicon valley", "software engineer",
        "product management", "cloud computing", "cybersecurity",
        "ph.d. computer science", "stanford", "mit", "carnegie mellon",
        "research scientist", "technical background"
    ]
    
    TECH_COMMITTEE_NAMES = [
        "technology committee", "digital committee", "innovation committee",
        "cybersecurity committee", "data committee", "ai committee",
        "technology and cybersecurity committee",
        "technology and innovation committee",
        "digital and technology committee",
        "information technology committee", "it oversight committee",
        "technology risk committee", "digital transformation committee"
    ]
    
    DATA_OFFICER_TITLES = [
        "chief technology officer", "chief information officer",
        "chief digital officer", "chief data officer", "chief ai officer",
        "chief analytics officer", "chief innovation officer",
        "vp technology", "vp engineering", "vp data",
        "head of technology", "head of ai", "head of data",'Chief Digital Officer', 'Chief Data Officer', 'Chief AI Officer', 'Chief Analytics Officer', 'Chief Innovation Officer', 'VP Technology', 'VP Engineering',
          'Chief Information Security Officer', 'CISO', 'Director of Technology', 'Director of Data Science', 'Director of AI', 'Director of Analytics', 'Director of Innovation', 'Head of Technology'
    ]
    
    EXCLUDE_COMMITTEES = [
        "audit committee", "compensation committee", "nominating committee",
        "governance committee", "executive committee"
    ]
    
    def analyze_company_governance(self, ticker: str) -> Optional[GovernanceSignal]:
        settings = get_settings()
        conn = get_connection()
        cur = conn.cursor()
        
        try:
            cur.execute(f"""
                SELECT c.id
                FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.companies c
                WHERE c.ticker = %s AND c.is_deleted = FALSE
            """, (ticker,))
            
            company_row = cur.fetchone()
            if not company_row:
                return None
            
            company_id = company_row[0]
            
            cur.execute(f"""
                SELECT dc.chunk_text
                FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.document_chunks dc
                JOIN {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.documents d
                    ON dc.document_id = d.id
                WHERE d.ticker = %s
                    AND d.filing_type = 'DEF 14A'
                ORDER BY d.filing_date DESC, dc.chunk_index
            """, (ticker,))
            
            rows = cur.fetchall()
            
            if not rows:
                return self._default_signal(company_id, ticker)
            
            all_text = " ".join([row[0] for row in rows if row[0]])
            
            return self._calculate_governance_score(company_id, ticker, all_text)
            
        finally:
            cur.close()
            conn.close()
    
    def _has_tech_committee(self, text: str) -> tuple:
        text_lower = text.lower()
        found = []
        
        for tc in self.TECH_COMMITTEE_NAMES:
            pattern = r'\b' + re.escape(tc) + r'\b'
            matches = list(re.finditer(pattern, text_lower))
            
            if matches:
                is_valid = True
                for match in matches:
                    start = max(0, match.start() - 20)
                    end = min(len(text_lower), match.end() + 20)
                    context = text_lower[start:end]
                    
                    if any(excl in context for excl in self.EXCLUDE_COMMITTEES):
                        is_valid = False
                        break
                
                if is_valid:
                    found.append(tc)
        
        return len(found) > 0, found
    
    def _has_ai_expertise(self, text: str) -> tuple:
        text_lower = text.lower()
        count = 0
        
        long_phrases = [kw for kw in self.AI_EXPERTISE_KEYWORDS if len(kw.split()) > 1]
        
        for phrase in long_phrases:
            if phrase in text_lower:
                count += 1
        
        return count > 0, count
    
    def _has_data_officer(self, text: str) -> bool:
        text_lower = text.lower()
        
        full_titles = [
            "chief technology officer",
            "chief information officer",
            "chief digital officer",
            "chief data officer",
            "chief ai officer"
        ]
        
        for title in full_titles:
            if title in text_lower:
                return True
        
        return False
    
    def _calculate_governance_score(
        self, 
        company_id: str, 
        ticker: str, 
        text: str
    ) -> GovernanceSignal:
        
        score = Decimal("20")
        
        has_tech, committees_found = self._has_tech_committee(text)
        if has_tech:
            score += Decimal("15")
        
        has_ai, tech_count = self._has_ai_expertise(text)
        if has_ai:
            score += Decimal("20")
        
        has_officer = self._has_data_officer(text)
        if has_officer:
            score += Decimal("15")
        
        text_lower = text.lower()
        has_independent = "independent director" in text_lower
        independent_ratio = Decimal("0.6") if has_independent else Decimal("0.4")
        if independent_ratio > Decimal("0.5"):
            score += Decimal("10")
        
        has_risk_tech = ("risk committee" in text_lower and 
                         "technology" in text_lower)
        if has_risk_tech:
            score += Decimal("10")
        
        has_ai_strategy = ("strategic" in text_lower and 
                          "artificial intelligence" in text_lower)
        if has_ai_strategy:
            score += Decimal("10")
        
        score = min(score, Decimal("100"))
        
        confidence = Decimal("0.5") + min(Decimal("0.45"), Decimal(str(len(text) / 100000)))
        confidence = min(confidence, Decimal("0.95"))
        
        return GovernanceSignal(
            company_id=UUID(company_id),
            ticker=ticker,
            governance_score=float(score),
            confidence=float(confidence),
            has_tech_committee=has_tech,
            has_ai_expertise=has_ai,
            has_data_officer=has_officer,
            has_risk_tech_oversight=has_risk_tech,
            has_ai_in_strategy=has_ai_strategy,
            tech_expertise_count=tech_count,
            independent_ratio=float(independent_ratio),
            ai_experts=[],
            relevant_committees=committees_found
        )
    
    def _default_signal(self, company_id: str, ticker: str) -> GovernanceSignal:
        return GovernanceSignal(
            company_id=UUID(company_id),
            ticker=ticker,
            governance_score=20.0,
            confidence=0.5,
            has_tech_committee=False,
            has_ai_expertise=False,
            has_data_officer=False,
            has_risk_tech_oversight=False,
            has_ai_in_strategy=False,
            tech_expertise_count=0,
            independent_ratio=0.5,
            ai_experts=[],
            relevant_committees=[]
        )

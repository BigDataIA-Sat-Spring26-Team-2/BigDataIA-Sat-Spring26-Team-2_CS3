# """
# Leadership Signal Collector - Analyzes executive commitment to AI/tech.

# Uses context-aware regex patterns to detect genuine AI leadership signals
# in SEC filings. Prioritizes precision over recall to avoid false positives.
# """

# import re
# from typing import List, Dict, Optional
# from uuid import UUID
# from datetime import datetime, timezone
# import structlog

# from app.models.signal import (
#     ExternalSignal,
#     SignalCategory,
#     SignalSource,
#     LeadershipSignalMetrics,
#     LeadershipEvidence
# )

# logger = structlog.get_logger(__name__)


# class LeadershipSignalCollector:
#     """
#     Analyzes SEC filings for leadership commitment signals.
    
#     Uses context-aware patterns to identify:
#     1. Tech-linked executive compensation (DEF-14A)
#     2. AI strategy statements (10-K Item 1)
#     3. Technology investments (10-K Item 7)
#     4. AI risk awareness (10-K Item 1A)
#     """
    
#     # ========================================================================
#     # COMPENSATION METRICS (DEF-14A Focus)
#     # Context: Executive pay tied to technology metrics
#     # ========================================================================
#     TECH_COMP_KEYWORDS = [
#         # Direct compensation linkage
#         r'(?:compensation|bonus|incentive|pay).*(?:tied to|linked to|based on|measured by).*(?:technology|digital|ai|innovation)',
#         r'(?:technology|digital|ai|innovation).*(?:compensation|bonus|incentive|performance metric)',
        
#         # KPI/metrics language
#         r'(?:technology|digital|ai).*(?:kpi|key performance indicator|metric|goal|target)',
#         r'(?:performance|bonus).*(?:technology|digital).*(?:transformation|modernization|initiative)',
        
#         # Executive tech roles
#         r'(?:cto|chief technology officer|chief digital officer|cdo).*(?:compensation|bonus|incentive)',
#         r'(?:chief information officer|cio).*(?:compensation|bonus|incentive)',
#         r'(?:technology|digital|innovation).*leadership.*(?:incentive|bonus|reward)',
        
#         # Transformation objectives
#         r'(?:it|technology).*(?:modernization|transformation|upgrade).*(?:objective|goal|metric)',
#         r'(?:digital|technology).*(?:strategy|initiative).*(?:bonus|incentive|compensation)',
        
#         # Innovation metrics
#         r'innovation.*(?:metric|kpi|goal).*(?:compensation|bonus)',
#         r'(?:technology|digital).*achievement.*(?:bonus|incentive)',
#     ]
    
#     # ========================================================================
#     # AI STRATEGY (10-K Item 1 Focus)
#     # Context: Strategic commitment to AI/ML
#     # ========================================================================
#     AI_STRATEGY_KEYWORDS = [
#         # Strategic investment statements
#         r'(?:investing|investment|committed|focus|focused|focusing)\s+(?:in|on|to)\s+(?:artificial intelligence|machine learning|ai\b|ml\b)',
#         r'(?:ai\b|artificial intelligence|machine learning)\s+(?:strategy|initiative|program|platform|capability)',
        
#         # Implementation/deployment
#         r'(?:deploying|implementing|developing|building)\s+(?:ai\b|artificial intelligence|machine learning)',
#         r'(?:ai\b|ml\b|artificial intelligence|machine learning)[-\s](?:powered|driven|enabled|based)\s+(?:solution|platform|system|application)',
        
#         # Future commitment
#         r'(?:plan to|intend to|will|planning to)\s+(?:deploy|implement|scale|expand).*(?:ai\b|artificial intelligence|machine learning)',
#         r'(?:ai\b|artificial intelligence|machine learning).*(?:transformation|adoption|integration)',
        
#         # Innovation leadership
#         r'(?:leading|pioneering|innovating|at the forefront).*(?:ai\b|artificial intelligence|machine learning)',
#         r'(?:ai\b|artificial intelligence).{0,50}(?:competitive advantage|differentiation|innovation)',
        
#         # Specific AI technologies
#         r'(?:natural language processing|nlp\b|computer vision|predictive analytics|recommendation engine)',
#         r'(?:generative ai|large language model|llm|neural network|deep learning)',
#         r'(?:automated|automation).*(?:ai\b|machine learning|artificial intelligence)',
        
#         # Advanced analytics (broader)
#         r'(?:advanced|predictive).*analytics.*(?:capability|platform|investment)',
#         r'data science.*(?:team|platform|capability|initiative)',
#     ]
    
#     # ========================================================================
#     # TECHNOLOGY INVESTMENT (10-K Item 7 MD&A Focus)
#     # Context: Actual dollar amounts for tech spending
#     # ========================================================================
#     TECH_INVESTMENT_KEYWORDS = [
#         # Dollar amounts with tech context
#         r'\$\s*\d+(?:\.\d+)?\s*(?:million|billion)\s+(?:in|for|toward|to)\s+(?:technology|ai\b|artificial intelligence|digital|it\b|cloud)',
#         r'(?:technology|ai\b|digital|cloud)\s+(?:investment|spending|budget|expenditure)\s+of\s+\$\s*\d+',
        
#         # Capital expenditure
#         r'(?:capital expenditure|capex).*(?:\$\s*\d+).*(?:technology|digital|ai\b|it\b)',
#         r'(?:technology|digital|ai\b).*(?:capital|capex).*(?:\$\s*\d+)',
        
#         # R&D investment
#         r'(?:research and development|r&d).*(?:\$\s*\d+).*(?:ai\b|artificial intelligence|machine learning|technology)',
#         r'(?:ai\b|artificial intelligence|machine learning).*(?:research|r&d).*(?:\$\s*\d+)',
        
#         # Infrastructure investment
#         r'(?:cloud|data center|infrastructure).*(?:investment|spending).*(?:\$\s*\d+)',
#         r'\$\s*\d+(?:\.\d+)?\s*(?:million|billion).*(?:technology infrastructure|it infrastructure|digital infrastructure)',
        
#         # Percentage allocations
#         r'\d+%.*(?:of|to).*(?:revenue|budget).*(?:technology|digital|ai\b)',
        
#         # Technology spending mentions (no dollar sign)
#         r'(?:increased|increasing|grew|growth in).*(?:technology|digital|it\b).*(?:spending|investment|expenditure)',
#         r'(?:technology|digital).*(?:investment|spending).*(?:increased|grew|growth)',
#     ]
    
#     # ========================================================================
#     # AI RISK AWARENESS (10-K Item 1A Focus)
#     # Context: Recognition of AI-related risks
#     # ========================================================================
#     AI_RISK_KEYWORDS = [
#         # Specific AI risks
#         r'(?:ai\b|artificial intelligence|machine learning).*(?:risk|risks|could|may|might).*(?:fail|malfunction|error|inaccurate)',
#         r'(?:algorithmic|algorithm).*(?:bias|discrimination|fairness|error)',
        
#         # Technology risk acknowledgment
#         r'(?:risk|risks).*(?:ai\b|artificial intelligence|machine learning|automated decision)',
#         r'(?:ai\b|artificial intelligence).*(?:ethical|ethics|bias|discrimination|privacy)',
        
#         # Data/model risks
#         r'(?:model|models|algorithm).*(?:risk|risks|could|may).*(?:inaccurate|biased|fail)',
#         r'(?:training data|data quality).*(?:risk|risks|could result in|may result in)',
        
#         # Regulatory risks
#         r'(?:regulation|regulatory|compliance).*(?:ai\b|artificial intelligence|algorithmic)',
#         r'(?:ai\b|artificial intelligence).*(?:regulation|regulatory|compliance|legal)',
        
#         # Cybersecurity + AI
#         r'(?:cybersecurity|cyber|security).*(?:ai\b|artificial intelligence|machine learning)',
#         r'(?:ai\b|artificial intelligence).*(?:security|breach|attack|vulnerability)',
        
#         # Operational risks
#         r'(?:reliance|dependence|dependent)\s+on.*(?:ai\b|artificial intelligence|machine learning|automated)',
#         r'(?:failure|disruption).*(?:ai\b|artificial intelligence|technology).*(?:system|platform)',
        
#         # Technology risks (broader)
#         r'(?:technology|digital).*(?:risk|risks|failure|disruption)',
#         r'(?:data|cyber).*(?:security|breach|privacy).*(?:risk|risks)',
#     ]

#     def __init__(self):
#         """Initialize the collector."""
#         self.logger = logger.bind(collector="leadership_signals")

#     async def analyze_company_leadership(
#         self,
#         company_id: UUID,
#         ticker: str,
#         document_chunks: List[Dict]
#     ) -> ExternalSignal:
#         """
#         Analyze leadership commitment from document chunks.
        
#         Args:
#             company_id: Company UUID
#             ticker: Company ticker symbol
#             document_chunks: List of document chunks from Snowflake
#                 Each dict should have: {
#                     'chunk_text': str,
#                     'filing_type': str,
#                     'section': str
#                 }
        
#         Returns:
#             ExternalSignal with leadership score
#         """
#         self.logger.info(
#             "analyzing_leadership",
#             company_id=str(company_id),
#             ticker=ticker,
#             chunks=len(document_chunks)
#         )
        
#         evidence: List[LeadershipEvidence] = []
        
#         # Analyze each chunk
#         for chunk in document_chunks:
#             chunk_text = chunk.get('chunk_text', '')
#             filing_type = chunk.get('filing_type', 'UNKNOWN')
#             section = chunk.get('section', 'unknown')
            
#             # Route to appropriate analyzer based on section
#             if 'compensation' in section.lower() or filing_type == 'DEF 14A':
#                 comp_evidence = self._analyze_compensation(
#                     chunk_text, filing_type, section
#                 )
#                 evidence.extend(comp_evidence)
                
#             if 'item_1' in section.lower() or 'business' in section.lower():
#                 strategy_evidence = self._analyze_strategy(
#                     chunk_text, filing_type, section
#                 )
#                 evidence.extend(strategy_evidence)
                
#             if 'item_7' in section.lower() or 'md&a' in section.lower() or 'mda' in section.lower():
#                 investment_evidence = self._analyze_investment(
#                     chunk_text, filing_type, section
#                 )
#                 evidence.extend(investment_evidence)
                
#             if 'item_1a' in section.lower() or 'risk' in section.lower():
#                 risk_evidence = self._analyze_risk(
#                     chunk_text, filing_type, section
#                 )
#                 evidence.extend(risk_evidence)
        
#         # Compute metrics
#         metrics = self._compute_metrics(evidence, len(document_chunks))
        
#         # Create signal
#         signal = ExternalSignal(
#             company_id=company_id,
#             category=SignalCategory.LEADERSHIP_SIGNALS,
#             source=SignalSource.COMPANY_WEBSITE,  # SEC filings = company disclosure
#             signal_date=datetime.now(timezone.utc),
#             raw_value=f"{len(evidence)} leadership signals detected",
#             normalized_score=round(metrics.composite_score, 1),
#             confidence=metrics.confidence,
#             metadata={
#                 'tech_comp_score': metrics.tech_comp_score,
#                 'ai_strategy_score': metrics.ai_strategy_score,
#                 'tech_investment_score': metrics.tech_investment_score,
#                 'ai_risk_score': metrics.ai_risk_score,
#                 'evidence_count': len(evidence),
#                 'filings_analyzed': metrics.filings_analyzed,
#                 'chunks_analyzed': metrics.total_sections,
#                 'top_evidence': [
#                     {
#                         'type': e.evidence_type,
#                         'snippet': e.text_snippet[:150],
#                         'keywords': e.keywords_matched[:3],  # Limit to 3 keywords
#                         'section': e.section,
#                         'filing_type': e.filing_type
#                     }
#                     for e in sorted(evidence, key=lambda x: x.confidence, reverse=True)[:5]
#                 ]
#             }
#         )
        
#         self.logger.info(
#             "leadership_analysis_complete",
#             ticker=ticker,
#             score=signal.normalized_score,
#             evidence_count=len(evidence),
#             breakdown={
#                 'compensation': metrics.tech_comp_score,
#                 'strategy': metrics.ai_strategy_score,
#                 'investment': metrics.tech_investment_score,
#                 'risk': metrics.ai_risk_score
#             }
#         )
        
#         return signal

#     def _analyze_compensation(
#         self, text: str, filing_type: str, section: str
#     ) -> List[LeadershipEvidence]:
#         """Analyze compensation structure for tech metrics."""
#         evidence = []
#         text_lower = text.lower()
        
#         for pattern in self.TECH_COMP_KEYWORDS:
#             matches = re.finditer(pattern, text_lower, re.IGNORECASE)
#             for match in matches:
#                 # Extract context (50 chars before and after)
#                 start = max(0, match.start() - 50)
#                 end = min(len(text), match.end() + 50)
#                 snippet = text[start:end].strip()
                
#                 # Clean up snippet
#                 snippet = ' '.join(snippet.split())  # Normalize whitespace
                
#                 evidence.append(LeadershipEvidence(
#                     evidence_type='compensation',
#                     text_snippet=snippet,
#                     filing_type=filing_type,
#                     section=section,
#                     confidence=0.85,
#                     keywords_matched=[match.group()]
#                 ))
        
#         return evidence

#     def _analyze_strategy(
#         self, text: str, filing_type: str, section: str
#     ) -> List[LeadershipEvidence]:
#         """Analyze strategic AI/tech statements."""
#         evidence = []
#         text_lower = text.lower()
        
#         for pattern in self.AI_STRATEGY_KEYWORDS:
#             matches = re.finditer(pattern, text_lower, re.IGNORECASE)
#             for match in matches:
#                 start = max(0, match.start() - 50)
#                 end = min(len(text), match.end() + 100)
#                 snippet = text[start:end].strip()
                
#                 snippet = ' '.join(snippet.split())
                
#                 evidence.append(LeadershipEvidence(
#                     evidence_type='strategy',
#                     text_snippet=snippet,
#                     filing_type=filing_type,
#                     section=section,
#                     confidence=0.90,
#                     keywords_matched=[match.group()]
#                 ))
        
#         return evidence

#     def _analyze_investment(
#         self, text: str, filing_type: str, section: str
#     ) -> List[LeadershipEvidence]:
#         """Analyze technology investment mentions."""
#         evidence = []
        
#         for pattern in self.TECH_INVESTMENT_KEYWORDS:
#             matches = re.finditer(pattern, text, re.IGNORECASE)
#             for match in matches:
#                 start = max(0, match.start() - 30)
#                 end = min(len(text), match.end() + 70)
#                 snippet = text[start:end].strip()
                
#                 snippet = ' '.join(snippet.split())
                
#                 evidence.append(LeadershipEvidence(
#                     evidence_type='investment',
#                     text_snippet=snippet,
#                     filing_type=filing_type,
#                     section=section,
#                     confidence=0.80,
#                     keywords_matched=[match.group()]
#                 ))
        
#         return evidence

#     def _analyze_risk(
#         self, text: str, filing_type: str, section: str
#     ) -> List[LeadershipEvidence]:
#         """Analyze AI/tech risk awareness."""
#         evidence = []
#         text_lower = text.lower()
        
#         for pattern in self.AI_RISK_KEYWORDS:
#             matches = re.finditer(pattern, text_lower, re.IGNORECASE)
#             for match in matches:
#                 start = max(0, match.start() - 50)
#                 end = min(len(text), match.end() + 100)
#                 snippet = text[start:end].strip()
                
#                 snippet = ' '.join(snippet.split())
                
#                 evidence.append(LeadershipEvidence(
#                     evidence_type='risk',
#                     text_snippet=snippet,
#                     filing_type=filing_type,
#                     section=section,
#                     confidence=0.75,
#                     keywords_matched=[match.group()]
#                 ))
        
#         return evidence

#     def _compute_metrics(
#         self, evidence: List[LeadershipEvidence], total_chunks: int
#     ) -> LeadershipSignalMetrics:
#         """Compute aggregate metrics from evidence."""
        
#         # Separate by type
#         comp_evidence = [e for e in evidence if e.evidence_type == 'compensation']
#         strategy_evidence = [e for e in evidence if e.evidence_type == 'strategy']
#         investment_evidence = [e for e in evidence if e.evidence_type == 'investment']
#         risk_evidence = [e for e in evidence if e.evidence_type == 'risk']
        
#         # Dedup by snippet to avoid counting same evidence multiple times
#         def dedup_evidence(evidence_list: List[LeadershipEvidence]) -> List[LeadershipEvidence]:
#             seen = set()
#             unique = []
#             for e in evidence_list:
#                 # Use first 100 chars as dedup key
#                 key = e.text_snippet[:100].lower()
#                 if key not in seen:
#                     seen.add(key)
#                     unique.append(e)
#             return unique
        
#         comp_evidence = dedup_evidence(comp_evidence)
#         strategy_evidence = dedup_evidence(strategy_evidence)
#         investment_evidence = dedup_evidence(investment_evidence)
#         risk_evidence = dedup_evidence(risk_evidence)
        
#         # Score each category
#         # Compensation: 20 points per unique evidence, max 100
#         comp_score = min(len(comp_evidence) * 20, 100)
        
#         # Strategy: 15 points per unique evidence, max 100
#         strategy_score = min(len(strategy_evidence) * 15, 100)
        
#         # Investment: 15 points per unique evidence, max 100
#         investment_score = min(len(investment_evidence) * 15, 100)
        
#         # Risk: 25 points per unique evidence, max 100
#         risk_score = min(len(risk_evidence) * 25, 100)
        
#         # Composite (weighted)
#         composite = (
#             0.40 * comp_score +
#             0.30 * strategy_score +
#             0.20 * investment_score +
#             0.10 * risk_score
#         )
        
#         # Confidence based on evidence volume and diversity
#         total_evidence = len(comp_evidence) + len(strategy_evidence) + len(investment_evidence) + len(risk_evidence)
#         categories_found = sum([
#             1 if comp_evidence else 0,
#             1 if strategy_evidence else 0,
#             1 if investment_evidence else 0,
#             1 if risk_evidence else 0
#         ])
        
#         # Base confidence on evidence count, boost for diversity
#         confidence = min(0.5 + (total_evidence / 50) + (categories_found * 0.05), 0.95)
        
#         return LeadershipSignalMetrics(
#             tech_comp_metrics_found=[e.text_snippet[:100] for e in comp_evidence[:5]],
#             tech_comp_score=comp_score,
#             ai_strategy_statements=[e.text_snippet[:100] for e in strategy_evidence[:5]],
#             ai_strategy_score=strategy_score,
#             tech_investment_mentions=[e.text_snippet[:100] for e in investment_evidence[:5]],
#             tech_investment_score=investment_score,
#             ai_risk_factors=[e.text_snippet[:100] for e in risk_evidence[:3]],
#             ai_risk_score=risk_score,
#             composite_score=composite,
#             confidence=confidence,
#             filings_analyzed=1,
#             total_sections=total_chunks
#         )

"""
Leadership Signal Collector - Analyzes executive commitment to AI/tech.

Filters out table of contents and focuses on substantive evidence.
"""

import re
from typing import List, Dict
from uuid import UUID
from datetime import datetime, timezone
import structlog

from app.models.signal import (
    ExternalSignal,
    SignalCategory,
    SignalSource,
    LeadershipSignalMetrics,
    LeadershipEvidence
)

logger = structlog.get_logger(__name__)


class LeadershipSignalCollector:
    """Analyzes SEC filings for leadership commitment signals."""
    
    TECH_COMP_KEYWORDS = [
        # Executive roles - with word boundaries to avoid "Secretary" matching "cto"
        r'\b(?:chief technology officer|chief digital officer|chief information officer)\b',
        r'\bcto\b.{0,200}(?:compensation|total pay|salary|bonus)',
        r'\bcdo\b.{0,200}(?:compensation|total pay|salary|bonus)',
        r'\bcio\b.{0,200}(?:compensation|total pay|salary|bonus)',
        
        # Direct linkage
        r'(?:compensation|bonus|incentive).{0,120}(?:tied to|linked to|based on|measured by).{0,120}(?:technology|digital|innovation)',
        r'(?:technology|digital|innovation).{0,120}(?:performance|metrics?|goals?|targets?)',
        
        # Long-term incentive plans
        r'(?:ltip|long[- ]term incentive).{0,200}(?:technology|digital)',
        
        # Transformation objectives
        r'(?:technology|digital).{0,150}(?:transformation|modernization).{0,150}(?:objective|metric|kpi)',
    ]
    
    AI_STRATEGY_KEYWORDS = [
        r'(?:investing|investment|committed|focus).{0,80}(?:in|on).{0,80}(?:artificial intelligence|machine learning|ai\b)',
        r'(?:ai\b|artificial intelligence|machine learning).{0,150}(?:strategy|initiative|program|platform|capability)',
        r'(?:deploying|implementing|developing|building).{0,120}(?:ai\b|artificial intelligence|machine learning)',
        r'(?:ai\b|ml\b|artificial intelligence|machine learning)[-\s](?:powered|driven|enabled|based)',
        r'(?:plan to|intend to|will).{0,80}(?:deploy|implement|scale).{0,120}(?:ai\b|artificial intelligence|machine learning)',
        r'(?:leading|pioneering).{0,150}(?:in|with).{0,100}(?:ai\b|artificial intelligence|machine learning)',
        r'\b(?:natural language processing|computer vision|predictive analytics|recommendation engine|generative ai|large language model|neural network|deep learning)\b',
        r'(?:advanced|predictive).{0,120}analytics',
        r'data science.{0,150}(?:team|platform|capability)',
        r'(?:developing|maintaining).{0,100}models?.{0,150}(?:machine learning|artificial intelligence)',
        r'(?:automation|automated).{0,150}(?:ai\b|artificial intelligence|machine learning)',
    ]
    
    TECH_INVESTMENT_KEYWORDS = [
    # Pattern 1: $X billion/million + tech keyword (flexible spacing)
    r'\$\s*\d+(?:\.\d+)?\s*(?:million|billion).{0,50}(?:in|for|on|to|toward).{0,50}(?:technology|digital|it\b|cloud)',
    r'\$\s*\d+(?:\.\d+)?\s*(?:million|billion).{0,100}(?:technology|digital|it\b)',
    
    # Pattern 2: Tech + spending/investment + $X
    r'(?:technology|digital|it\b).{0,100}(?:spending|investment|expenditure).{0,100}\$\s*\d+',
    
    # Pattern 3: Spent/invested $X + tech
    r'(?:spent|invested).{0,100}\$\s*\d+.{0,100}(?:technology|digital|it\b)',
    
    # Pattern 4: Technology expenses (common in financial statements)
    r'(?:technology|it\b).{0,80}(?:expense|expenses|cost|costs)',
    
    # Pattern 5: Capital expenditure
    r'(?:capital|capex).{0,200}(?:technology|it\b)',
    
    # Pattern 6: Technology investment (no $ required)
    r'(?:technology|digital|it\b).{0,100}(?:investment|spending)',
    
    # Pattern 7: Increased tech spending
    r'(?:technology|digital|it\b).{0,150}(?:increased|grew|growth)',
    ]
    
    AI_RISK_KEYWORDS = [
        r'(?:ai\b|artificial intelligence|machine learning).{0,200}(?:risk|could|may).{0,120}(?:fail|error|inaccurate|malfunction)',
        r'(?:algorithmic|algorithm).{0,150}(?:bias|discrimination|error)',
        r'(?:risk|risks).{0,150}(?:ai\b|artificial intelligence|machine learning)',
        r'(?:ai\b|artificial intelligence).{0,200}(?:bias|discrimination|ethics|privacy)',
        r'(?:model|models).{0,200}(?:risk|inaccurate|biased|fail)',
        r'(?:regulation|regulatory).{0,200}(?:ai\b|artificial intelligence)',
        r'(?:cyber|security).{0,200}(?:ai\b|artificial intelligence|machine learning)',
        r'(?:reliance|dependence).{0,200}(?:ai\b|artificial intelligence|automated)',
        r'(?:failure|disruption).{0,200}(?:ai\b|artificial intelligence).{0,100}(?:system|platform)',
    ]

    def __init__(self):
        self.logger = logger.bind(collector="leadership_signals")
    
    def _is_table_of_contents(self, text: str) -> bool:
        """Detect if text is a table of contents or navigation."""
        text_sample = text[:800]
        
        toc_patterns = [
            r'\d+\s+(?:PROPOSAL|Item|Section|Chapter)',
            r'(?:page|pg\.)\s*\d+',
            r'\.\s*\.\s*\.\s*\.',
            r'\d+\s+\w+\s+\d+\s+\w+\s+\d+',
            r'(?:Table of Contents|INDEX|CONTENTS)',
        ]
        
        matches = sum(1 for p in toc_patterns if re.search(p, text_sample, re.IGNORECASE))
        
        return matches >= 2

    async def analyze_company_leadership(
        self,
        company_id: UUID,
        ticker: str,
        document_chunks: List[Dict]
    ) -> ExternalSignal:
        self.logger.info(
            "analyzing_leadership",
            company_id=str(company_id),
            ticker=ticker,
            chunks=len(document_chunks)
        )
        
        evidence: List[LeadershipEvidence] = []
        
        comp_chunks_analyzed = 0
        strategy_chunks_analyzed = 0
        investment_chunks_analyzed = 0
        risk_chunks_analyzed = 0
        toc_filtered = 0
        
        for chunk in document_chunks:
            chunk_text = chunk.get('chunk_text', '')
            filing_type = chunk.get('filing_type', 'UNKNOWN')
            section = chunk.get('section', 'unknown')
            
            # Filter TOC chunks
            if self._is_table_of_contents(chunk_text):
                toc_filtered += 1
                continue
            
            if 'compensation' in section.lower() or filing_type == 'DEF 14A':
                comp_chunks_analyzed += 1
                comp_evidence = self._analyze_compensation(chunk_text, filing_type, section)
                evidence.extend(comp_evidence)
                
            if 'item_1' in section.lower() or 'business' in section.lower():
                strategy_chunks_analyzed += 1
                strategy_evidence = self._analyze_strategy(chunk_text, filing_type, section)
                evidence.extend(strategy_evidence)
                
            if 'item_7' in section.lower() or 'item_2' in section.lower() or 'mda' in section.lower():
                investment_chunks_analyzed += 1
                investment_evidence = self._analyze_investment(chunk_text, filing_type, section)
                evidence.extend(investment_evidence)
                
            if 'item_1a' in section.lower() or 'risk' in section.lower():
                risk_chunks_analyzed += 1
                risk_evidence = self._analyze_risk(chunk_text, filing_type, section)
                evidence.extend(risk_evidence)
        
        self.logger.info(
            "routing_stats",
            comp_chunks=comp_chunks_analyzed,
            strategy_chunks=strategy_chunks_analyzed,
            investment_chunks=investment_chunks_analyzed,
            risk_chunks=risk_chunks_analyzed,
            toc_filtered=toc_filtered
        )
        
        metrics = self._compute_metrics(evidence, len(document_chunks))
        
        signal = ExternalSignal(
            company_id=company_id,
            category=SignalCategory.LEADERSHIP_SIGNALS,
            source=SignalSource.COMPANY_WEBSITE,
            signal_date=datetime.now(timezone.utc),
            raw_value=f"{len(evidence)} leadership signals detected",
            normalized_score=round(metrics.composite_score, 1),
            confidence=metrics.confidence,
            metadata={
                'tech_comp_score': metrics.tech_comp_score,
                'ai_strategy_score': metrics.ai_strategy_score,
                'tech_investment_score': metrics.tech_investment_score,
                'ai_risk_score': metrics.ai_risk_score,
                'evidence_count': len(evidence),
                'filings_analyzed': metrics.filings_analyzed,
                'chunks_analyzed': metrics.total_sections,
                'toc_chunks_filtered': toc_filtered,
                'routing_stats': {
                    'comp_chunks': comp_chunks_analyzed,
                    'strategy_chunks': strategy_chunks_analyzed,
                    'investment_chunks': investment_chunks_analyzed,
                    'risk_chunks': risk_chunks_analyzed
                },
                'top_evidence': [
                    {
                        'type': e.evidence_type,
                        'snippet': e.text_snippet[:150],
                        'keywords': e.keywords_matched[:3],
                        'section': e.section,
                        'filing_type': e.filing_type
                    }
                    for e in sorted(evidence, key=lambda x: x.confidence, reverse=True)[:5]
                ]
            }
        )
        
        self.logger.info(
            "leadership_analysis_complete",
            ticker=ticker,
            score=signal.normalized_score,
            evidence_count=len(evidence)
        )
        
        return signal

    def _analyze_compensation(self, text: str, filing_type: str, section: str) -> List[LeadershipEvidence]:
        evidence = []
        
        for pattern in self.TECH_COMP_KEYWORDS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                start = max(0, match.start() - 50)
                end = min(len(text), match.end() + 50)
                snippet = ' '.join(text[start:end].split())
                
                evidence.append(LeadershipEvidence(
                    evidence_type='compensation',
                    text_snippet=snippet,
                    filing_type=filing_type,
                    section=section,
                    confidence=0.85,
                    keywords_matched=[match.group()[:50]]
                ))
        
        return evidence

    def _analyze_strategy(self, text: str, filing_type: str, section: str) -> List[LeadershipEvidence]:
        evidence = []
        
        for pattern in self.AI_STRATEGY_KEYWORDS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                start = max(0, match.start() - 50)
                end = min(len(text), match.end() + 100)
                snippet = ' '.join(text[start:end].split())
                
                evidence.append(LeadershipEvidence(
                    evidence_type='strategy',
                    text_snippet=snippet,
                    filing_type=filing_type,
                    section=section,
                    confidence=0.90,
                    keywords_matched=[match.group()[:50]]
                ))
        
        return evidence

    def _analyze_investment(self, text: str, filing_type: str, section: str) -> List[LeadershipEvidence]:
        evidence = []
        
        for pattern in self.TECH_INVESTMENT_KEYWORDS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                start = max(0, match.start() - 30)
                end = min(len(text), match.end() + 70)
                snippet = ' '.join(text[start:end].split())
                
                evidence.append(LeadershipEvidence(
                    evidence_type='investment',
                    text_snippet=snippet,
                    filing_type=filing_type,
                    section=section,
                    confidence=0.80,
                    keywords_matched=[match.group()[:50]]
                ))
        
        return evidence

    def _analyze_risk(self, text: str, filing_type: str, section: str) -> List[LeadershipEvidence]:
        evidence = []
        
        for pattern in self.AI_RISK_KEYWORDS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                start = max(0, match.start() - 50)
                end = min(len(text), match.end() + 100)
                snippet = ' '.join(text[start:end].split())
                
                evidence.append(LeadershipEvidence(
                    evidence_type='risk',
                    text_snippet=snippet,
                    filing_type=filing_type,
                    section=section,
                    confidence=0.75,
                    keywords_matched=[match.group()[:50]]
                ))
        
        return evidence

    def _compute_metrics(self, evidence: List[LeadershipEvidence], total_chunks: int) -> LeadershipSignalMetrics:
        comp_evidence = [e for e in evidence if e.evidence_type == 'compensation']
        strategy_evidence = [e for e in evidence if e.evidence_type == 'strategy']
        investment_evidence = [e for e in evidence if e.evidence_type == 'investment']
        risk_evidence = [e for e in evidence if e.evidence_type == 'risk']
        
        self.logger.info(
            "evidence_before_dedup",
            compensation=len(comp_evidence),
            strategy=len(strategy_evidence),
            investment=len(investment_evidence),
            risk=len(risk_evidence)
        )
        
        def dedup_evidence(evidence_list: List[LeadershipEvidence]) -> List[LeadershipEvidence]:
            seen = set()
            unique = []
            
            for e in evidence_list:
                text = e.text_snippet.lower()
                text = re.sub(r'\s+', ' ', text)
                
                words = [w for w in text.split() if len(w) > 4 and w.isalpha()]
                
                if len(words) >= 20:
                    key_words = words[5:20]
                else:
                    key_words = words[:15]
                
                key = ' '.join(key_words)
                
                if key not in seen:
                    seen.add(key)
                    unique.append(e)
            
            return unique
        
        comp_evidence = dedup_evidence(comp_evidence)
        strategy_evidence = dedup_evidence(strategy_evidence)
        investment_evidence = dedup_evidence(investment_evidence)
        risk_evidence = dedup_evidence(risk_evidence)
        
        self.logger.info(
            "evidence_after_dedup",
            compensation=len(comp_evidence),
            strategy=len(strategy_evidence),
            investment=len(investment_evidence),
            risk=len(risk_evidence)
        )
        
        comp_score = min(len(comp_evidence) * 20, 100)
        strategy_score = min(len(strategy_evidence) * 15, 100)
        investment_score = min(len(investment_evidence) * 15, 100)
        risk_score = min(len(risk_evidence) * 25, 100)
        
        composite = (
            0.40 * comp_score +
            0.30 * strategy_score +
            0.20 * investment_score +
            0.10 * risk_score
        )
        
        total_evidence = len(comp_evidence) + len(strategy_evidence) + len(investment_evidence) + len(risk_evidence)
        categories_found = sum([
            1 if comp_evidence else 0,
            1 if strategy_evidence else 0,
            1 if investment_evidence else 0,
            1 if risk_evidence else 0
        ])
        
        confidence = min(0.5 + (total_evidence / 50) + (categories_found * 0.05), 0.95)
        
        self.logger.info(
            "final_scores",
            compensation=comp_score,
            strategy=strategy_score,
            investment=investment_score,
            risk=risk_score,
            composite=composite,
            confidence=confidence
        )
        
        return LeadershipSignalMetrics(
            tech_comp_metrics_found=[e.text_snippet[:100] for e in comp_evidence[:5]],
            tech_comp_score=comp_score,
            ai_strategy_statements=[e.text_snippet[:100] for e in strategy_evidence[:5]],
            ai_strategy_score=strategy_score,
            tech_investment_mentions=[e.text_snippet[:100] for e in investment_evidence[:5]],
            tech_investment_score=investment_score,
            ai_risk_factors=[e.text_snippet[:100] for e in risk_evidence[:3]],
            ai_risk_score=risk_score,
            composite_score=composite,
            confidence=confidence,
            filings_analyzed=1,
            total_sections=total_chunks
        )
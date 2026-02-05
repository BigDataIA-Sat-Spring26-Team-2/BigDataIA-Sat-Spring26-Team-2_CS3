# # app/pipelines/leadership_signals.py

# from typing import List
# from uuid import UUID
# from datetime import datetime, timezone

# import structlog
# from app.pipelines.collectors.hardcoded_collector import get_hardcoded_executives
# from app.models.signal import ExternalSignal, SignalCategory, SignalSource
# from app.models.leadership import LeadershipEvidence, ExecutiveProfile

# logger = structlog.get_logger(__name__)


# class LeadershipSignalCollector:
#     """Collect leadership signals from company websites."""
    
#     def __init__(self):
#         from app.pipelines.collectors.website_collector import CompanyWebsiteCollector
#         from app.pipelines.collectors.news_collector import NewsAPICollector
        
#         self.website_collector = CompanyWebsiteCollector()
#         self.news_collector = NewsAPICollector()
#         self.logger = logger.bind(collector="leadership_orchestrator")
    
#     async def analyze_company_leadership(
#         self,
#         company_id: UUID,
#         ticker: str,
#         company_name: str
#     ) -> ExternalSignal:
#         """Analyze company leadership AI commitment."""
        
#         self.logger.info("Starting analysis", ticker=ticker, company=company_name)
        
#         # Collect executives
#         # Collect executives
#         all_executives = await self.website_collector.collect_leadership_data(company_name, ticker)

#         if not all_executives:
#             self.logger.warning(
#         "No executives scraped from website – falling back to generic leadership baseline",
#             ticker=ticker
#     )   
#             all_executives = get_hardcoded_executives(ticker)

#     # 🔹 Create a single synthetic generic executive
#             all_executives = [
#                 ExecutiveProfile(
#                     name="Unknown Executive Team",
#                     title="Senior Executive Leadership",
#                     role_weight=0.75,
#                     indicators=[],
#                 sources=["Company Website (Generic – Fallback)"]
#         )
#         ]

#     # Ensure score calculation works
#         all_executives[0].calculate_max_score()


#         ai_executives = [e for e in all_executives if 'AI-Relevant' in ' '.join(e.sources)]
#         generic_executives = [e for e in all_executives if 'Generic' in ' '.join(e.sources)]

#         self.logger.info(
#         "Executive classification",
#         total=len(all_executives),
#         ai_relevant=len(ai_executives),
#         generic=len(generic_executives)
#         )
#         if ai_executives:
#     # Tier 1: Has AI leadership - use only AI executives
#             executives_to_score = ai_executives
#             penalty_multiplier = 1.0
#             tier = "AI Leadership Present"
#             self.logger.info("Using Tier 1: AI leadership found", count=len(ai_executives))
#         else:
#     # Tier 2: No AI leadership - use all executives with penalty
#             executives_to_score = generic_executives if generic_executives else all_executives
#             penalty_multiplier = 0.5
#             tier = "No AI Leadership (Penalty Applied)"
#             self.logger.warning("Using Tier 2: No AI leadership, applying 50% penalty")

# # Calculate score
#         evidence = LeadershipEvidence(
#             ticker=ticker,
#             company_name=company_name,
#             research_date=datetime.now(timezone.utc),
#             executives=executives_to_score,
#             sources_used=['website'],
#             total_sources=1
#             )

#         raw_score = evidence.calculate_leadership_score()
#         leadership_score = raw_score * penalty_multiplier

#         self.logger.info(
#             "Score calculated",
#             raw=raw_score,
#             penalty=penalty_multiplier,
#             final=leadership_score,
#             tier=tier
#         )
        
#         # # Calculate score
#         # evidence = LeadershipEvidence(
#         #     ticker=ticker,
#         #     company_name=company_name,
#         #     research_date=datetime.now(timezone.utc),
#         #     executives=executives,
#         #     sources_used=['website'],
#         #     total_sources=1
#         # )
        
#         # leadership_score = evidence.calculate_leadership_score()
#         confidence = min(0.5 + (len(all_executives) / 20), 0.95)
        
#         # Create signal with ALL required metadata
#         signal = ExternalSignal(
#             company_id=company_id,
#             category=SignalCategory.LEADERSHIP_SIGNALS,
#             source=SignalSource.COMPANY_WEBSITE,
#             signal_date=datetime.now(timezone.utc),
#             raw_value=f"{len(all_executives)} executives analyzed",
#             normalized_score=round(leadership_score, 1),
#             confidence=confidence,
#             metadata={
#                 'executives_analyzed': len(all_executives),
#                 'sources_used': ['website'],
#                 'website_score': round(leadership_score, 1),
#                 'news_bonus': 0.0,
#                 'ai_executives': len(ai_executives),  # ✅ ADD
#                 'generic_executives': len(generic_executives),  # ✅ ADD
#                 'tier': tier,  # ✅ ADD
#                 'penalty_multiplier': penalty_multiplier,  # ✅ ADD
#                 'raw_score': raw_score,  # ✅ ADD
#                 'executive_details': [
#                     {
#                         'name': e.name,
#                         'title': e.title,
#                         'role_weight': e.role_weight,
#                         'ai_score': e.max_indicator_score,
#                         'is_ai_relevant': 'AI-Relevant' in ' '.join(e.sources),
#                         'indicators': [
#                             {
#                                 'type': ind.type.value,
#                                 'score': ind.score,
#                                 'evidence': ind.evidence[:100]
#                             }
#                             for ind in e.indicators
#                         ]
#                     }
#                     for e in sorted(executives_to_score, key=lambda x: x.role_weight, reverse=True)
#                 ]
#             }
#         )
        
#         self.logger.info("Analysis complete", ticker=ticker, score=leadership_score, executives=len(executives_to_score))
        
#         return signal
    
#     def _create_empty_signal(self, company_id: UUID, ticker: str) -> ExternalSignal:
#         """Create zero-score signal"""
        
#         return ExternalSignal(
#             company_id=company_id,
#             category=SignalCategory.LEADERSHIP_SIGNALS,
#             source=SignalSource.COMPANY_WEBSITE,
#             signal_date=datetime.now(timezone.utc),
#             raw_value="No executives found",
#             normalized_score=0.0,
#             confidence=0.0,
#             metadata={
#                 'error': 'No executives discovered',
#                 'executives_analyzed': 0,
#                 'ai_executives': 0,
#                 'generic_executives': 0,
#                 'tier': 'No Data',  # ✅ ADD THIS
#                 'penalty_multiplier': 0.0,  # ✅ ADD THIS
#                 'raw_score': 0.0,  # ✅ ADD THIS
#                 'sources_used': ['website'],
#                 'website_score': 0.0,
#                 'news_bonus': 0.0,
#                 'executive_details': []
#             }
#         )
    
#     async def close(self):
#         """Cleanup"""
#         await self.website_collector.close()
#         await self.news_collector.close()


# app/pipelines/leadership_signals.py

from typing import List
from uuid import UUID
from datetime import datetime, timezone

import structlog
from app.pipelines.collectors.hardcoded_collector import get_hardcoded_executives
from app.models.signal import ExternalSignal, SignalCategory, SignalSource
from app.models.leadership import LeadershipEvidence, ExecutiveProfile

logger = structlog.get_logger(__name__)


class LeadershipSignalCollector:
    """Collect leadership signals from company websites."""
    
    def __init__(self):
        from app.pipelines.collectors.website_collector import CompanyWebsiteCollector
        from app.pipelines.collectors.news_collector import NewsAPICollector
        
        self.website_collector = CompanyWebsiteCollector()
        self.news_collector = NewsAPICollector()
        self.logger = logger.bind(collector="leadership_orchestrator")
    
    async def analyze_company_leadership(
        self,
        company_id: UUID,
        ticker: str,
        company_name: str
    ) -> ExternalSignal:
        """Analyze company leadership AI commitment."""
        
        self.logger.info("Starting analysis", ticker=ticker, company=company_name)
        
        # 1️⃣ Try website scraping
        all_executives = await self.website_collector.collect_leadership_data(
            company_name, ticker
        )

        # 2️⃣ If website scraping fails → use hardcoded executives
        if not all_executives:
            self.logger.warning(
                "No executives scraped from website – trying hardcoded executives",
                ticker=ticker
            )
            all_executives = get_hardcoded_executives(ticker)

        # 3️⃣ If STILL empty → final synthetic fallback
        if not all_executives:
            self.logger.warning(
                "No hardcoded executives found – using synthetic fallback",
                ticker=ticker
            )
            all_executives = [
                ExecutiveProfile(
                    name="Unknown Executive Team",
                    title="Senior Executive Leadership",
                    role_weight=0.75,
                    indicators=[],
                    sources=["Company Website (Generic – Fallback)"]
                )
            ]
            all_executives[0].calculate_max_score()

        # Classify executives
        ai_executives = [e for e in all_executives if 'AI-Relevant' in ' '.join(e.sources)]
        generic_executives = [e for e in all_executives if 'Generic' in ' '.join(e.sources)]

        self.logger.info(
            "Executive classification",
            total=len(all_executives),
            ai_relevant=len(ai_executives),
            generic=len(generic_executives)
        )

        # Scoring tier logic
        if ai_executives:
    # ✅ Use BOTH AI + Generic executives
            executives_to_score = ai_executives + generic_executives
            penalty_multiplier = 1.0
            tier = "AI Leadership Present"
            self.logger.info(
                "Using Tier 1: AI leadership found",
                ai=len(ai_executives),
                generic=len(generic_executives)
            )
        else:
            executives_to_score = generic_executives if generic_executives else all_executives
            penalty_multiplier = 0.5
            tier = "No AI Leadership (Penalty Applied)"
            self.logger.warning("Using Tier 2: No AI leadership, applying 50% penalty")

        # Score calculation
        evidence = LeadershipEvidence(
            ticker=ticker,
            company_name=company_name,
            research_date=datetime.now(timezone.utc),
            executives=executives_to_score,
            sources_used=['website'],
            total_sources=1
        )

        raw_score = evidence.calculate_leadership_score()
        leadership_score = raw_score * penalty_multiplier

        self.logger.info(
            "Score calculated",
            raw=raw_score,
            penalty=penalty_multiplier,
            final=leadership_score,
            tier=tier
        )

        confidence = min(0.5 + (len(all_executives) / 20), 0.95)

        signal = ExternalSignal(
            company_id=company_id,
            category=SignalCategory.LEADERSHIP_SIGNALS,
            source=SignalSource.COMPANY_WEBSITE,
            signal_date=datetime.now(timezone.utc),
            raw_value=f"{len(all_executives)} executives analyzed",
            normalized_score=round(leadership_score, 1),
            confidence=confidence,
            metadata={
                'executives_analyzed': len(all_executives),
                'sources_used': ['website'],
                'website_score': round(leadership_score, 1),
                'news_bonus': 0.0,
                'ai_executives': len(ai_executives),
                'generic_executives': len(generic_executives),
                'tier': tier,
                'penalty_multiplier': penalty_multiplier,
                'raw_score': raw_score,
                'executive_details': [
                    {
                        'name': e.name,
                        'title': e.title,
                        'role_weight': e.role_weight,
                        'ai_score': e.max_indicator_score,
                        'is_ai_relevant': 'AI-Relevant' in ' '.join(e.sources),
                        'indicators': [
                            {
                                'type': ind.type.value,
                                'score': ind.score,
                                'evidence': ind.evidence[:100]
                            }
                            for ind in e.indicators
                        ]
                    }
                    for e in sorted(
                        executives_to_score,
                        key=lambda x: x.role_weight,
                        reverse=True
                    )
                ]
            }
        )

        self.logger.info(
            "Analysis complete",
            ticker=ticker,
            score=leadership_score,
            executives=len(executives_to_score)
        )

        return signal
    
    async def close(self):
        await self.website_collector.close()
        await self.news_collector.close()

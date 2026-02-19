import httpx
import structlog
from typing import Dict, Any, List
from decimal import Decimal
from uuid import UUID

from app.scoring.evidence_mapper import EvidenceMapper, EvidenceScore, SignalSource, Dimension
from app.scoring.rubric_scorer import RubricScorer
from app.scoring.talent_concentration import TalentConcentrationCalculator
from app.scoring.position_factor import PositionFactorCalculator
from app.scoring.vr_calculator import VRCalculator
from app.scoring.hr_calculator import HRCalculator
from app.scoring.synergy_calculator import SynergyCalculator
from app.scoring.confidence_calculator import ConfidenceCalculator
from app.pipelines.glassdoor_collector import GlassdoorCultureCollector, GlassdoorCollectionPipeline
from app.pipelines.board_analyzer import BoardCompositionAnalyzer
from app.services.evidence_counter import get_total_evidence_count, get_evidence_breakdown  # ✅ NEW

logger = structlog.get_logger()


class ScoringIntegrationService:
    """
    Full pipeline: CS1/CS2 data → Org-AI-R score.
    CS3 Task 6.0b implementation.
    """

    def __init__(
        self,
        cs1_api_url: str = "http://localhost:8000",
        cs2_api_url: str = "http://localhost:8001",
    ):
        self.cs1_url = cs1_api_url
        self.cs2_url = cs2_api_url

        # Initialize all components
        self.evidence_mapper = EvidenceMapper()
        self.rubric_scorer = RubricScorer()
        self.tc_calculator = TalentConcentrationCalculator()
        self.pf_calculator = PositionFactorCalculator()
        self.vr_calculator = VRCalculator()
        self.hr_calculator = HRCalculator()
        self.synergy_calculator = SynergyCalculator()
        self.ci_calculator = ConfidenceCalculator()
        self.glassdoor_collector = GlassdoorCultureCollector()
        self.board_analyzer = BoardCompositionAnalyzer()

        self.http = httpx.Client(timeout=30.0)

    def score_company(
        self, 
        ticker: str,
        market_cap_percentile: float = 0.5
    ) -> Dict[str, Any]:
        """
        Run the full Org-AI-R scoring pipeline for a ticker.

        Args:
            ticker: Company ticker symbol
            market_cap_percentile: Market cap percentile within sector (0-1)

        Returns:
            Complete assessment with all calculation details
        """
        logger.info("score_company_started", ticker=ticker, market_cap_percentile=market_cap_percentile)

        # Step 1: Fetch company ────────────────────────────────────────────
        company = self._fetch_company(ticker)
        company_id = company["id"]
        sector = company.get("sector", "business_services")
        industry_id = company.get("industry_id")

        logger.info(
            "company_fetched",
            ticker=ticker,
            company_id=company_id,
            sector=sector,
            industry_id=industry_id,
        )

        # Step 2: Fetch CS2 evidence ───────────────────────────────────────
        cs2_evidence = self._fetch_cs2_evidence(company_id)
        logger.info(
            "cs2_evidence_fetched",
            signal_count=len(cs2_evidence.get("signals", [])),
        )

        # Step 3: Collect Glassdoor ────────────────────────────────────────
        glassdoor = self._collect_glassdoor(company_id, ticker)
        logger.info(
            "glassdoor_collected",
            overall_score=glassdoor.get("overall_score"),
            review_count=glassdoor.get("review_count"),
        )

        # Step 4: Collect Board ────────────────────────────────────────────
        board = self._collect_board(company_id, ticker)
        logger.info(
            "board_collected",
            governance_score=board.get("governance_score"),
        )

        # Step 5: Build evidence scores ────────────────────────────────────
        evidence_scores = self._build_evidence_scores(cs2_evidence, glassdoor, board)
        logger.info("evidence_scores_built", count=len(evidence_scores))

        # Step 6: Map to dimensions ────────────────────────────────────────
        dimension_score_objects = self.evidence_mapper.map_evidence_to_dimensions(evidence_scores)
        dimension_scores: Dict[str, float] = {
            dim.value: float(ds.score)
            for dim, ds in dimension_score_objects.items()
        }

        # Step 7: Calculate talent concentration ───────────────────────────
        job_postings_raw = cs2_evidence.get("job_postings", [])
        job_analysis = self.tc_calculator.analyze_job_postings(job_postings_raw)
        individual_mentions = int(glassdoor.get("individual_mentions", 0))
        review_count = max(1, int(glassdoor.get("review_count", 1)))
        tc_decimal = self.tc_calculator.calculate_tc(
            job_analysis=job_analysis,
            glassdoor_individual_mentions=individual_mentions,
            glassdoor_review_count=review_count,
        )
        tc = float(tc_decimal)
        logger.info("talent_concentration_calculated", tc=tc)

        # Step 8: Calculate V^R ────────────────────────────────────────────
        vr_result = self.vr_calculator.calculate(
            dimension_scores=dimension_scores,
            talent_concentration=tc,
            sector=sector,
        )
        logger.info("vr_calculated", vr_score=float(vr_result.vr_score))

        # Step 9: Calculate Position Factor + H^R ──────────────────────────
        position_factor_decimal = self.pf_calculator.calculate_position_factor(
            vr_score=float(vr_result.vr_score),
            sector=sector,
            market_cap_percentile=market_cap_percentile,  # ✅ Use user input
        )
        position_factor = float(position_factor_decimal)

        hr_result = self.hr_calculator.calculate(
            sector=sector,
            position_factor=position_factor,
            industry_id=industry_id,
        )
        logger.info(
            "hr_calculated",
            hr_score=float(hr_result.hr_score),
            position_factor=position_factor,
        )

        # Step 10: Calculate Synergy ───────────────────────────────────────
        alignment = self._calculate_alignment(vr_result, hr_result)

        synergy_result = self.synergy_calculator.calculate(
            vr_score=float(vr_result.vr_score),
            hr_score=float(hr_result.hr_score),
            alignment=alignment,
            timing_factor=1.0,
        )
        logger.info("synergy_calculated", synergy_score=float(synergy_result.synergy_score))

        alpha = Decimal("0.60")  # Idiosyncratic weight
        beta = Decimal("0.12")   # Synergy weight

        weighted_components = (
            alpha * vr_result.vr_score + 
            (Decimal("1") - alpha) * hr_result.hr_score
        )
        final_score = (
            (Decimal("1") - beta) * weighted_components + 
            beta * synergy_result.synergy_score
        )
        
        # Clamp to [0, 100]
        final_score = max(Decimal("0"), min(Decimal("100"), final_score))
        
        logger.info("org_air_score_computed", final_score=float(final_score))

        # Step 11: Calculate Confidence Interval ───────────────────────────
        total_evidence = get_total_evidence_count(UUID(company_id))
        evidence_breakdown_dict = get_evidence_breakdown(UUID(company_id))
        
        logger.info(
            "evidence_summary",
            ticker=ticker,
            total_evidence=total_evidence,
            breakdown={k: v["evidence_count"] for k, v in evidence_breakdown_dict.items()}
        )

        ci_result = self.ci_calculator.calculate(
            score=float(final_score),
            score_type="org_air",
            evidence_count=total_evidence,
        )

        # Step 12: Build result
        result = {
            "company_id": company_id,
            "ticker": ticker,
            "sector": sector,
            
            # Core scores
            "vr_score": float(vr_result.vr_score),
            "hr_score": float(hr_result.hr_score),
            "synergy_score": float(synergy_result.synergy_score),
            "final_score": float(final_score),
            
            "position_factor": position_factor,
            "talent_concentration": tc,
            "market_cap_percentile": market_cap_percentile,
            
            # Confidence
            "ci_lower": float(ci_result.ci_lower),
            "ci_upper": float(ci_result.ci_upper),
            "confidence": float(ci_result.confidence),
            "sem": float(ci_result.sem),
            
            # Evidence
            "evidence_count": total_evidence,
            "evidence_breakdown": {k: v["evidence_count"] for k, v in evidence_breakdown_dict.items()},
            
            # Dimension scores
            "dimension_scores": dimension_scores,
            
            # V^R components (for calculation_details)
            "vr_components": {
                "weighted_mean": float(vr_result.weighted_mean),
                "cv": float(vr_result.cv),
                "cv_penalty": float(vr_result.cv_penalty),
                "cv_penalty_amount": float(vr_result.cv_penalty_amount),
                "tc": float(vr_result.talent_concentration),
                "tc_penalty": float(vr_result.talent_risk_adj),
                "tc_penalty_amount": float(vr_result.tc_penalty_amount),
            },
            
            # H^R components (for calculation_details)
            "hr_components": {
                "hr_base": float(hr_result.hr_base),
                "position_adjustment": float(hr_result.position_adjustment),
            },
            
            # Synergy components (for calculation_details)
            "synergy_components": {
                "base_synergy": float(synergy_result.base_synergy),
                "alignment": float(synergy_result.alignment),
                "timing_factor": float(synergy_result.timing_factor),
            },
            
            # Formula constants
            "formula_constants": {
                "alpha": 0.60,
                "beta": 0.12,
            }
        }

        # Step 13: Persist
        self._persist_assessment(result)

        logger.info(
            "score_company_completed",
            ticker=ticker,
            final_score=float(final_score),
            evidence_count=total_evidence,
        )
        
        return result


    def _fetch_company(self, ticker: str) -> Dict[str, Any]:
        """Step 1: Fetch from CS1 API"""
        url = f"{self.cs1_url}/api/v1/companies"
        response = self.http.get(url, params={"page_size": 100})
        response.raise_for_status()
        data = response.json()

        items = data.get("items", [])
        for company in items:
            if company.get("ticker", "").upper() == ticker.upper():
                if "market_cap_percentile" not in company:
                    company["market_cap_percentile"] = 0.5
                return company

        raise ValueError(f"Company not found in CS1 for ticker={ticker!r}")

    def _fetch_cs2_evidence(self, company_id: str) -> Dict[str, Any]:
        """Step 2: Fetch from CS2 API"""
        url = f"{self.cs2_url}/api/v1/signals"
        response = self.http.get(
            url,
            params={"company_id": company_id, "limit": 200},
        )
        response.raise_for_status()
        data = response.json()

        all_items = data.get("items", [])
        job_postings = [
            item for item in all_items
            if item.get("category") == "technology_hiring"
        ]

        return {"signals": all_items, "job_postings": job_postings}

    def _collect_glassdoor(self, company_id: str, ticker: str) -> Dict[str, Any]:
        """Step 3: Collect Glassdoor culture signal"""
        _fallback = {
            "overall_score": 50.0,
            "individual_mentions": 0,
            "review_count": 1,
            "confidence": 0.5,
        }
        try:
            pipeline = GlassdoorCollectionPipeline()
            signal = pipeline.collect_and_analyze(company_id, ticker)
            raw = signal.__dict__
            return {
                "overall_score": float(raw.get("overall_score", 50.0)),
                "innovation_score": float(raw.get("innovation_score", 50.0)),
                "data_driven_score": float(raw.get("data_driven_score", 50.0)),
                "change_readiness_score": float(raw.get("change_readiness_score", 50.0)),
                "ai_awareness_score": float(raw.get("ai_awareness_score", 50.0)),
                "review_count": int(raw.get("review_count", 1)),
                "confidence": float(raw.get("confidence", 0.5)),
                "individual_mentions": int(raw.get("individual_mentions", 0)),
                "avg_rating": float(raw.get("avg_rating", 0.0)),
            }
        except Exception as exc:
            logger.warning(
                "glassdoor_collection_failed",
                company_id=company_id,
                ticker=ticker,
                error=str(exc),
            )
            return _fallback

    def _collect_board(self, company_id: str, ticker: str) -> Dict[str, Any]:
        """Step 4: Collect board composition signal"""
        _fallback = {"governance_score": 50.0, "confidence": 0.5}
        try:
            result = self.board_analyzer.analyze_company_governance(ticker)
            if result is None:
                return _fallback
            return {
                "governance_score": float(result.governance_score),
                "confidence": float(result.confidence),
                "has_tech_committee": result.has_tech_committee,
                "has_ai_expertise": result.has_ai_expertise,
                "has_data_officer": result.has_data_officer,
                "tech_expertise_count": result.tech_expertise_count,
            }
        except Exception as exc:
            logger.warning(
                "board_collection_failed",
                company_id=company_id,
                ticker=ticker,
                error=str(exc),
            )
            return _fallback

    def _build_evidence_scores(
        self,
        cs2_evidence: Dict[str, Any],
        glassdoor: Dict[str, Any],
        board: Dict[str, Any],
    ) -> List[EvidenceScore]:
        """Step 5: Build EvidenceScore list from all sources"""
        evidence_scores: List[EvidenceScore] = []

        # CS2 signals
        for signal in cs2_evidence.get("signals", []):
            try:
                source = SignalSource(signal["category"])
            except (ValueError, KeyError):
                logger.debug(
                    "signal_category_skipped",
                    category=signal.get("category"),
                )
                continue

            score = Decimal(str(signal.get("normalized_score", 50)))
            conf = Decimal(str(signal.get("confidence", 0.5)))
            evidence_scores.append(
                EvidenceScore(
                    source=source,
                    score=score,
                    confidence=conf,
                    raw_value=str(signal.get("raw_value", "")),
                    metadata=signal.get("metadata", {}),
                )
            )

        # Glassdoor
        glassdoor_score = Decimal(str(glassdoor.get("overall_score", 50)))
        glassdoor_conf = Decimal(str(glassdoor.get("confidence", 0.5)))
        evidence_scores.append(
            EvidenceScore(
                source=SignalSource.GLASSDOOR_REVIEWS,
                score=glassdoor_score,
                confidence=glassdoor_conf,
                raw_value="glassdoor_overall",
                metadata={
                    "review_count": glassdoor.get("review_count", 0),
                    "individual_mentions": glassdoor.get("individual_mentions", 0),
                },
            )
        )

        # Board composition
        board_score = Decimal(str(board.get("governance_score", 50)))
        board_conf = Decimal(str(board.get("confidence", 0.5)))
        evidence_scores.append(
            EvidenceScore(
                source=SignalSource.BOARD_COMPOSITION,
                score=board_score,
                confidence=board_conf,
                raw_value="board_composition",
                metadata=board,
            )
        )

        return evidence_scores

    def _calculate_alignment(self, vr_result, hr_result) -> float:
        """
        Calculate alignment between V^R and H^R.
        
        Formula: Alignment = 1.0 - |V^R - H^R| / 100
        
        Perfect alignment (same scores) = 1.0
        Maximum misalignment (100 points apart) = 0.0
        """
        vr = float(vr_result.vr_score)
        hr = float(hr_result.hr_score)
        alignment = 1.0 - abs(vr - hr) / 100.0
        return max(0.0, min(1.0, alignment))

    def _persist_assessment(self, result: Dict[str, Any]) -> None:
        """
        Step 13: Persist assessment to CS1 database.
        
        Creates assessment with all calculation details stored.
        """
        # Build calculation details JSON
        calculation_details = {
            "vr_components": result.get("vr_components", {}),
            "hr_components": result.get("hr_components", {}),
            "synergy_components": result.get("synergy_components", {}),
            "evidence_breakdown": result.get("evidence_breakdown", {}),
            "dimension_scores": result.get("dimension_scores", {}),
            "formula_constants": result.get("formula_constants", {}),
            "market_cap_percentile": result.get("market_cap_percentile"),
        }

        url = f"{self.cs1_url}/api/v1/assessments"
        payload = {
            "company_id": result["company_id"],
            "assessment_type": "screening",
            "assessment_date": "2026-02-18",
            "primary_assessor": "CS3_Integration_Service",
            "status": "submitted",
            
            # Scores
            "v_r_score": result["vr_score"],
            "hr_score": result["hr_score"],
            "synergy_score": result["synergy_score"],
            "final_score": result["final_score"],
            
            # Metrics
            "position_factor": result["position_factor"],
            "talent_concentration": result["talent_concentration"],
            "evidence_count": result["evidence_count"],
            
            # Confidence
            "confidence_lower": result["ci_lower"],
            "confidence_upper": result["ci_upper"],
            "confidence_level": result["confidence"],
            
            # Full breakdown
            "calculation_details": calculation_details,
        }

        try:
            resp = self.http.post(url, json=payload)
            resp.raise_for_status()
            assessment_id = resp.json().get("id")
            logger.info(
                "assessment_persisted",
                ticker=result["ticker"],
                assessment_id=assessment_id,
            )
        except Exception as exc:
            logger.error(
                "assessment_persist_failed",
                ticker=result["ticker"],
                error=str(exc),
            )
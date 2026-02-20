"""
CS3 Task 6.0b: ScoringIntegrationService

Full pipeline: CS1/CS2 data → Org-AI-R score.

Evidence flow:
  CS1 API (company) + CS2 API (signals) + Glassdoor (S3) + Board (Snowflake)
  → EvidenceMapper → 7 DimensionScores
  → VRCalculator  → V^R score
  → HRCalculator  → H^R score
  → Synergy calc  → alignment-adjusted combined score
  → CI calculator → confidence interval
  → persist to CS1
"""

import json
import httpx
import structlog
from typing import Dict, Any, List
from decimal import Decimal
from uuid import UUID, uuid4
from datetime import date, datetime, timezone
from app.config import get_settings
from app.services.snowflake import get_connection
from app.scoring.evidence_mapper import EvidenceMapper, EvidenceScore, SignalSource, Dimension
from app.scoring.evidence_helpers import get_dimension_evidence
from app.scoring.rubric_scorer import RubricScorer
from app.scoring.talent_concentration import TalentConcentrationCalculator
from app.scoring.position_factor import PositionFactorCalculator
from app.scoring.vr_calculator import VRCalculator
from app.scoring.hr_calculator import HRCalculator
from app.scoring.synergy_calculator import SynergyCalculator
from app.scoring.confidence_calculator import ConfidenceCalculator
from app.pipelines.glassdoor_collector import GlassdoorCultureCollector, GlassdoorCollectionPipeline
from app.pipelines.board_analyzer import BoardCompositionAnalyzer
from app.services.evidence_counter import get_total_evidence_count, get_evidence_breakdown
from app.config import get_settings
from app.services.snowflake import get_connection

logger = structlog.get_logger()


class ScoringIntegrationService:

    def __init__(
        self,
        cs1_api_url: str = "http://localhost:8000"
    ):
        self.cs1_url = cs1_api_url

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
        self.http = httpx.Client(timeout=300.0)


    def score_company(self, ticker: str,  market_cap_percentile: float = 0.5) -> Dict[str, Any]:
        """
        Run the full Org-AI-R scoring pipeline for a ticker.

        Args:
            ticker: Company ticker symbol
            market_cap_percentile: Market cap percentile within sector (0-1)

        Returns:
            Complete assessment with all calculation details
        """
        logger.info("score_company_started", ticker=ticker)

        # Step 1: Fetch company ────────────────────────────────────────────
        company = self._fetch_company(ticker)
        company_id = company["id"]
        industry_id = company.get("industry_id")
        sector = self._get_sector_from_db(company_id)

        logger.info(
            "company_fetched",
            ticker=ticker,
            company_id=company_id,
            sector=sector,
            market_cap_percentile=market_cap_percentile,
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

        # Step 6b: Run Rubric Scorer (Path B) and blend with Path A ─────────
        path_a_scores = dict(dimension_scores)  # save raw Path A
        path_b_scores: Dict[str, Any] = {}

        BLEND_DIMENSIONS = [
            "data_infrastructure", "ai_governance", "technology_stack",
            "talent", "leadership", "use_case_portfolio", "culture",
        ]
        for dim_name in BLEND_DIMENSIONS:
            try:
                evidence_text, metrics = get_dimension_evidence(
                    company_id, ticker, dim_name
                )
                if evidence_text:
                    rubric_result = self.rubric_scorer.score_dimension(
                        dim_name, evidence_text, metrics
                    )
                    path_b_scores[dim_name] = {
                        "score": float(rubric_result.score),
                        "level": str(rubric_result.level),
                        "rationale": rubric_result.rationale,
                    }
            except Exception as e:
                logger.warning(
                    "rubric_scoring_failed_integration",
                    dimension=dim_name,
                    error=str(e),
                )

        # Blend: Combined = 0.6 * Path A + 0.4 * Path B
        for dim_name in BLEND_DIMENSIONS:
            if dim_name in path_b_scores:
                pa = path_a_scores[dim_name]
                pb = path_b_scores[dim_name]["score"]
                blended = round(pa * 0.6 + pb * 0.4, 2)
                dimension_scores[dim_name] = max(0.0, min(100.0, blended))

        logger.info(
            "path_ab_blended",
            path_a_count=len(path_a_scores),
            path_b_count=len(path_b_scores),
            blended_dims=list(path_b_scores.keys()),
        )

        # Step 7: Talent concentration ────────────────────────────────────────
        # Build JobAnalysis from pre-aggregated metadata in EXTERNAL_SIGNALS
        job_postings_raw = cs2_evidence.get("job_postings", [])
        if job_postings_raw and isinstance(job_postings_raw[0].get("metadata"), dict):
            meta = job_postings_raw[0]["metadata"]
            seniority = meta.get("seniority_distribution", {})
            from app.scoring.talent_concentration import JobAnalysis
            job_analysis = JobAnalysis(
                total_ai_jobs=int(meta.get("ai_jobs", 0)),
                senior_ai_jobs=int(seniority.get("senior", 0)) + int(seniority.get("executive", 0)),
                mid_ai_jobs=int(seniority.get("mid", 0)),
                entry_ai_jobs=int(seniority.get("entry", 0)),
                unique_skills=set(meta.get("skills_found", [])),
            )
        else:
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
            market_cap_percentile=market_cap_percentile,
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
            "org_air_score": float(final_score),
            "final_score": float(final_score),

            # Alignment & contributing factors
            "alignment": alignment,
            "talent_concentration": tc,
            "position_factor": position_factor,
            "market_cap_percentile": market_cap_percentile,

            # Confidence interval
            "ci_lower": float(ci_result.ci_lower),
            "ci_upper": float(ci_result.ci_upper),
            "confidence": float(ci_result.confidence),
            "sem": float(ci_result.sem),

            # Dimension detail
            "dimension_scores": dimension_scores,

            # VR penalty breakdown for transparency
            "vr_weighted_mean": float(vr_result.weighted_mean),
            "vr_cv": float(vr_result.cv),
            "vr_cv_penalty_amount": float(vr_result.cv_penalty_amount),
            "vr_tc_penalty_amount": float(vr_result.tc_penalty_amount),

            # Path A / Path B breakdown
            "path_a_scores": path_a_scores,
            "path_b_scores": path_b_scores,

            # Evidence provenance
            "evidence_count": total_evidence,
            "evidence_breakdown": {k: v["evidence_count"] for k, v in evidence_breakdown_dict.items()},
            "glassdoor_review_count": glassdoor.get("review_count", 0),
            "board_governance_score": board.get("governance_score", 50.0),

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
            },
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


    def _get_sector_from_db(self, company_id: str) -> str:
        """Look up sector by joining companies → industries in Snowflake."""
        from app.services.snowflake import get_connection
        from app.config import get_settings

        settings = get_settings()
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(f"""
                SELECT i.sector
                FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.companies c
                JOIN {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.industries i
                  ON c.industry_id = i.id
                WHERE c.id = %s AND c.is_deleted = FALSE
            """, (str(company_id),))
            row = cur.fetchone()
            if row and row[0]:
                sector = row[0].lower().strip()
                logger.info("sector_resolved", company_id=company_id, sector=sector)
                return sector
        except Exception as exc:
            logger.warning("sector_lookup_failed", company_id=company_id, error=str(exc))
        finally:
            cur.close()
            conn.close()

        logger.warning("sector_not_found_using_default", company_id=company_id)
        return "business_services"

    def _fetch_company(self, ticker: str) -> Dict[str, Any]:
        """
        Step 1: Query Snowflake directly for company by ticker.
        """
        settings = get_settings()
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(f"""
                SELECT id, name, ticker, industry_id, position_factor
                FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.companies
                WHERE UPPER(ticker) = %s AND is_deleted = FALSE
            """, (ticker.upper(),))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Company not found for ticker={ticker!r}")
            return {
                "id": row[0],
                "name": row[1],
                "ticker": row[2],
                "industry_id": row[3],
                "position_factor": float(row[4]) if row[4] else 0.0,
                "market_cap_percentile": 0.5,
            }
        finally:
            cur.close()
            conn.close()

    def _fetch_cs2_evidence(self, company_id: str) -> Dict[str, Any]:
        """
        Step 2: Query Snowflake directly for external signals.
        Returns dict with 'signals' (all items) and 'job_postings'
        (items where category == 'technology_hiring').
        """
        settings = get_settings()
        table = f"{settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.EXTERNAL_SIGNALS"
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(f"""
                SELECT id, company_id, category, source, signal_date,
                       raw_value, normalized_score, confidence, metadata
                FROM {table}
                WHERE company_id = %s
                ORDER BY signal_date DESC, created_at DESC
                LIMIT 200
            """, (str(company_id),))
            rows = cur.fetchall()
        finally:
            cur.close()
            conn.close()

        all_items = []
        for r in rows:
            meta = r[8]
            if isinstance(meta, str):
                meta = json.loads(meta) if meta else {}
            elif meta is None:
                meta = {}
            all_items.append({
                "id": r[0],
                "company_id": r[1],
                "category": r[2],
                "source": r[3],
                "signal_date": str(r[4]) if r[4] else None,
                "raw_value": r[5],
                "normalized_score": float(r[6]) if r[6] is not None else 50.0,
                "confidence": float(r[7]) if r[7] is not None else 0.5,
                "metadata": meta,
            })

        job_postings = [
            item for item in all_items
            if item.get("category") == "technology_hiring"
        ]

        return {"signals": all_items, "job_postings": job_postings}

    def _collect_glassdoor(self, company_id: str, ticker: str) -> Dict[str, Any]:
        """
        Step 3: Load Glassdoor culture signal.
        Priority: EXTERNAL_SIGNALS table → S3 reviews → neutral fallback.
        """
        _fallback = {
            "overall_score": 50.0,
            "individual_mentions": 0,
            "review_count": 1,
            "confidence": 0.5,
        }

        try:
            settings = get_settings()
            conn = get_connection()
            cur = conn.cursor()
            try:
                cur.execute(f"""
                    SELECT normalized_score, confidence, metadata
                    FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.EXTERNAL_SIGNALS
                    WHERE company_id = %s
                      AND category = 'culture' AND source = 'glassdoor'
                    ORDER BY signal_date DESC
                    LIMIT 1
                """, (str(company_id),))
                row = cur.fetchone()
            finally:
                cur.close()
                conn.close()

            if row:
                meta = row[2]
                if isinstance(meta, str):
                    meta = json.loads(meta) if meta else {}
                elif meta is None:
                    meta = {}

                comp = meta.get("component_scores", {})
                result = {
                    "overall_score": float(row[0]) if row[0] is not None else 50.0,
                    "confidence": float(row[1]) if row[1] is not None else 0.5,
                    "review_count": int(meta.get("review_count", 1)),
                    "avg_rating": float(meta.get("avg_rating", 0.0)),
                    "current_employee_ratio": float(meta.get("current_employee_ratio", 0.0)),
                    "innovation_score": float(comp.get("innovation", 50.0)),
                    "data_driven_score": float(comp.get("data_driven", 50.0)),
                    "change_readiness_score": float(comp.get("change_readiness", 50.0)),
                    "ai_awareness_score": float(comp.get("ai_awareness", 50.0)),
                    "individual_mentions": 0,
                    "positive_keywords": meta.get("positive_keywords", []),
                    "negative_keywords": meta.get("negative_keywords", []),
                }
                logger.info(
                    "glassdoor_from_external_signals",
                    company_id=company_id,
                    ticker=ticker,
                    overall_score=result["overall_score"],
                    review_count=result["review_count"],
                )
                return result
        except Exception as exc:
            logger.warning(
                "glassdoor_external_signals_lookup_failed",
                company_id=company_id,
                error=str(exc),
            )

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
                "glassdoor_s3_collection_failed",
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


    def _persist_assessment(self, result: Dict[str, Any]) -> str:
        settings = get_settings()
        conn = None
        cur = None

        try:
            conn = get_connection()
            cur = conn.cursor()
            
            company_id = result["company_id"]
            
            # DEDUPLICATION: Check for existing assessment for this company
            check_sql = f"""
                SELECT id, created_at
                FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.assessments
                WHERE company_id = %s
                ORDER BY created_at DESC
                LIMIT 1
            """
            
            cur.execute(check_sql, (company_id,))
            existing = cur.fetchone()
            
            # Build calculation details JSON
            calculation_details = {
                "vr_components": result.get("vr_components", {}),
                "hr_components": result.get("hr_components", {}),
                "synergy_components": result.get("synergy_components", {}),
                "evidence_breakdown": result.get("evidence_breakdown", {}),
                "dimension_scores": result.get("dimension_scores", {}),
                "formula_constants": result.get("formula_constants", {}),
            }
            
            if existing:
                # UPDATE existing assessment
                assessment_id = existing[0]
                existing_created = existing[1]
                
                logger.info(
                    "existing_assessment_found",
                    company_id=company_id,
                    assessment_id=assessment_id,
                    existing_created=existing_created,
                    action="updating"
                )
                
                update_sql = f"""
                    UPDATE {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.assessments
                    SET
                        assessment_date = %s,
                        v_r_score = %s,
                        hr_score = %s,
                        synergy_score = %s,
                        final_score = %s,
                        position_factor = %s,
                        talent_concentration = %s,
                        market_cap_percentile = %s,
                        evidence_count = %s,
                        confidence_level = %s,
                        sem = %s,
                        ci_lower = %s,
                        ci_upper = %s,
                        calculation_details = PARSE_JSON(%s)
                    WHERE id = %s
                """
                
                cur.execute(
                    update_sql,
                    (
                        date.today(),
                        result["vr_score"],
                        result["hr_score"],
                        result["synergy_score"],
                        result["final_score"],
                        result["position_factor"],
                        result["talent_concentration"],
                        result["market_cap_percentile"],
                        result["evidence_count"],
                        result["confidence"],
                        result["sem"],
                        result["ci_lower"],
                        result["ci_upper"],
                        json.dumps(calculation_details),
                        assessment_id,
                    ),
                )
                
                logger.info(
                    "assessment_updated",
                    ticker=result["ticker"],
                    assessment_id=assessment_id,
                    final_score=result["final_score"]
                )
                
            else:
                # INSERT new assessment
                assessment_id = str(uuid4())
                
                logger.info(
                    "no_existing_assessment",
                    company_id=company_id,
                    action="inserting_new"
                )
                
                insert_sql = f"""
                    INSERT INTO {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.assessments (
                        id, company_id, assessment_date,
                        v_r_score, hr_score, synergy_score, final_score,
                        position_factor, talent_concentration, market_cap_percentile,
                        evidence_count, confidence_level, sem, ci_lower, ci_upper,
                        calculation_details,
                        created_at
                    )
                    SELECT
                        %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s, %s,
                        PARSE_JSON(%s),
                        %s
                """
                
                cur.execute(
                    insert_sql,
                    (
                        assessment_id,
                        company_id,
                        date.today(),
                        result["vr_score"],
                        result["hr_score"],
                        result["synergy_score"],
                        result["final_score"],
                        result["position_factor"],
                        result["talent_concentration"],
                        result["market_cap_percentile"],
                        result["evidence_count"],
                        result["confidence"],
                        result["sem"],
                        result["ci_lower"],
                        result["ci_upper"],
                        json.dumps(calculation_details),
                        datetime.now(timezone.utc),
                    ),
                )
                
                logger.info(
                    "assessment_inserted",
                    ticker=result["ticker"],
                    assessment_id=assessment_id,
                    final_score=result["final_score"]
                )
            
            conn.commit()
            
            logger.info(
                "assessment_persisted",
                ticker=result["ticker"],
                assessment_id=assessment_id,
                final_score=result["final_score"],
                evidence_count=result["evidence_count"],
                was_update=existing is not None
            )
            
            return assessment_id
            
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(
                "assessment_persist_failed",
                ticker=result.get("ticker"),
                error=str(e)
            )
            raise
            
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

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
import structlog
from typing import Dict, Any, List, Optional
from decimal import Decimal
from uuid import uuid4

from app.config import get_settings
from app.services.snowflake import get_connection
from app.scoring.evidence_mapper import EvidenceMapper, EvidenceScore, SignalSource, Dimension
from app.scoring.evidence_helpers import get_dimension_evidence
from app.scoring.rubric_scorer import RubricScorer
from app.scoring.talent_concentration import TalentConcentrationCalculator
from app.scoring.position_factor import PositionFactorCalculator
from app.scoring.vr_calculator import VRCalculator
from app.scoring.hr_calculator import HRCalculator
from app.pipelines.glassdoor_collector import GlassdoorCultureCollector, GlassdoorCollectionPipeline
from app.pipelines.board_analyzer import BoardCompositionAnalyzer


# ---------------------------------------------------------------------------
# Adapter wrappers — insulate this service from teammate naming changes
# ---------------------------------------------------------------------------

def _load_synergy_calculator():
    """
    Adapter: load synergy calculator regardless of class name.
    Tries known names in order. Returns an object with a .calculate() method.
    """
    try:
        from app.scoring.synergy_calculator import SynergyCalculator
        return SynergyCalculator()
    except ImportError:
        pass
    try:
        # teammate may have named it differently
        import importlib, inspect
        mod = importlib.import_module("app.scoring.synergy_calculator")
        for name, obj in inspect.getmembers(mod, inspect.isclass):
            if "synergy" in name.lower() or "Synergy" in name:
                return obj()
        # last resort: return first class in module
        classes = [obj for _, obj in inspect.getmembers(mod, inspect.isclass)]
        if classes:
            return classes[0]()
    except Exception:
        pass
    return None


def _load_confidence_calculator():
    """
    Adapter: load confidence calculator regardless of class name.
    Tries known names in order. Returns an object with a .calculate() method.
    """
    try:
        from app.scoring.confidence import ConfidenceCalculator
        return ConfidenceCalculator()
    except ImportError:
        pass
    try:
        import importlib, inspect
        mod = importlib.import_module("app.scoring.confidence")
        for name, obj in inspect.getmembers(mod, inspect.isclass):
            if "confidence" in name.lower() or "Confidence" in name:
                return obj()
        classes = [obj for _, obj in inspect.getmembers(mod, inspect.isclass)]
        if classes:
            return classes[0]()
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

logger = structlog.get_logger()


class ScoringIntegrationService:
    """
    Full pipeline: CS1/CS2 data → Org-AI-R score.
    CS3 Task 6.0b implementation.
    """

    def __init__(self):
        # Confirmed existing components
        self.evidence_mapper = EvidenceMapper()
        self.rubric_scorer = RubricScorer()
        self.tc_calculator = TalentConcentrationCalculator()
        self.pf_calculator = PositionFactorCalculator()
        self.vr_calculator = VRCalculator()
        self.hr_calculator = HRCalculator()
        self.glassdoor_collector = GlassdoorCultureCollector()
        self.board_analyzer = BoardCompositionAnalyzer()

        # Teammate modules — loaded via adapters, may be None if not yet created
        self.synergy_calculator = _load_synergy_calculator()
        self.ci_calculator = _load_confidence_calculator()

        if not self.synergy_calculator:
            logger.warning("synergy_calculator_not_available")
        if not self.ci_calculator:
            logger.warning("confidence_calculator_not_available")

    # -----------------------------------------------------------------------
    # Public entry point
    # -----------------------------------------------------------------------

    def score_company(self, ticker: str) -> Dict[str, Any]:
        """
        Run the full Org-AI-R scoring pipeline for a ticker.

        Steps:
          1  Fetch company metadata from CS1
          2  Fetch CS2 external signals
          3  Collect Glassdoor culture signal
          4  Collect board composition signal
          5  Build EvidenceScore list
          6  Map evidence → 7 dimension scores
          7  Calculate talent concentration (TC)
          8  Calculate V^R
          9  Calculate H^R (requires position factor)
          10 Calculate synergy / alignment → Org-AI-R score
          11 Calculate confidence interval
          12 Build result dict
          13 Persist assessment to CS1
        """
        logger.info("score_company_started", ticker=ticker)

        # Step 1 ─────────────────────────────────────────────────────────────
        company = self._fetch_company(ticker)
        company_id = company["id"]
        sector = self._get_sector_from_db(company_id)
        market_cap_percentile = float(company.get("market_cap_percentile", 0.5))

        logger.info(
            "company_fetched",
            ticker=ticker,
            company_id=company_id,
            sector=sector,
            market_cap_percentile=market_cap_percentile,
        )

        # Step 2 ─────────────────────────────────────────────────────────────
        cs2_evidence = self._fetch_cs2_evidence(company_id)
        logger.info(
            "cs2_evidence_fetched",
            signal_count=len(cs2_evidence.get("signals", [])),
            job_signal_count=len(cs2_evidence.get("job_postings", [])),
        )

        # Step 3 ─────────────────────────────────────────────────────────────
        glassdoor = self._collect_glassdoor(company_id, ticker)
        logger.info(
            "glassdoor_collected",
            overall_score=glassdoor.get("overall_score"),
            review_count=glassdoor.get("review_count"),
        )

        # Step 4 ─────────────────────────────────────────────────────────────
        board = self._collect_board(company_id, ticker)
        logger.info(
            "board_collected",
            governance_score=board.get("governance_score"),
        )

        # Step 5 ─────────────────────────────────────────────────────────────
        evidence_scores: List[EvidenceScore] = self._build_evidence_scores(
            cs2_evidence, glassdoor, board
        )
        logger.info("evidence_scores_built", count=len(evidence_scores))

        # Step 6 ─────────────────────────────────────────────────────────────
        dimension_score_objects = self.evidence_mapper.map_evidence_to_dimensions(
            evidence_scores
        )
        # VRCalculator expects Dict[str, float]
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

        # Step 8: V^R ─────────────────────────────────────────────────────────
        vr_result = self.vr_calculator.calculate(
            dimension_scores=dimension_scores,
            talent_concentration=tc,
            sector=sector,
        )
        logger.info("vr_calculated", vr_score=float(vr_result.vr_score))

        # Step 9: Position factor + H^R ───────────────────────────────────────
        position_factor_decimal = self.pf_calculator.calculate_position_factor(
            vr_score=float(vr_result.vr_score),
            sector=sector,
            market_cap_percentile=market_cap_percentile,
        )
        position_factor = float(position_factor_decimal)

        hr_result = self.hr_calculator.calculate(
            sector=sector,
            position_factor=position_factor,
        )
        logger.info(
            "hr_calculated",
            hr_score=float(hr_result.hr_score),
            position_factor=position_factor,
        )

        # Step 10: Alignment + synergy → Org-AI-R score ───────────────────────
        alignment = self._calculate_alignment(vr_result, hr_result)

        if self.synergy_calculator is not None:
            try:
                synergy_result = self.synergy_calculator.calculate(
                    vr_score=vr_result.vr_score,
                    hr_score=hr_result.hr_score,
                    alignment=alignment,
                    timing_factor=Decimal("1.0"),
                )
                # Duck-type: try attribute then dict access
                try:
                    synergy_score = Decimal(str(synergy_result.synergy_score))
                except AttributeError:
                    try:
                        synergy_score = Decimal(str(synergy_result["synergy_score"]))
                    except (KeyError, TypeError):
                        synergy_score = Decimal(str(synergy_result)) if synergy_result is not None else Decimal("0")
            except Exception as exc:
                logger.warning("synergy_calculator_failed", error=str(exc))
                synergy_score = self._inline_synergy(vr_result, hr_result, alignment)
        else:
            synergy_score = self._inline_synergy(vr_result, hr_result, alignment)

        logger.info("synergy_calculated", synergy_score=float(synergy_score))

        # Org-AI-R = weighted combination adjusted by alignment
        # VR carries 70% weight (company-specific readiness);
        # HR carries 30% weight (industry context).
        # Alignment multiplier: perfect alignment → full score, misalignment penalises.
        alignment_multiplier = Decimal("0.80") + Decimal("0.20") * Decimal(str(alignment))
        org_air_raw = (
            Decimal("0.70") * vr_result.vr_score
            + Decimal("0.30") * hr_result.hr_score
        ) * alignment_multiplier
        final_score = max(Decimal("0"), min(Decimal("100"), org_air_raw))
        logger.info("org_air_score_computed", final_score=float(final_score))

        # Step 11: Confidence interval ────────────────────────────────────────
        total_evidence = len(evidence_scores)
        ci_lower, ci_upper, confidence = self._calculate_ci(
            final_score=final_score,
            total_evidence=total_evidence,
        )

        # Step 12: Build result dict ──────────────────────────────────────────
        result = {
            "company_id": company_id,
            "ticker": ticker,
            "sector": sector,
            # Core scores
            "vr_score": float(vr_result.vr_score),
            "hr_score": float(hr_result.hr_score),
            "synergy_score": float(synergy_score),
            "org_air_score": float(final_score),
            # Confidence interval
            "ci_lower": float(ci_lower),
            "ci_upper": float(ci_upper),
            "confidence": float(confidence),
            # Contributing factors
            "alignment": alignment,
            "talent_concentration": tc,
            "position_factor": position_factor,
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
            "glassdoor_review_count": review_count,
            "board_governance_score": board.get("governance_score", 50.0),
        }

        # Step 13: Persist ────────────────────────────────────────────────────
        self._persist_assessment(result)

        logger.info(
            "score_company_completed",
            ticker=ticker,
            org_air_score=float(final_score),
            confidence=float(confidence),
        )
        return result

    # -----------------------------------------------------------------------
    # Step helpers
    # -----------------------------------------------------------------------

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

        # --- Primary: read from EXTERNAL_SIGNALS table ---
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

        # --- Secondary: try S3 via GlassdoorCollectionPipeline ---
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
        """
        Step 4: Analyze board composition from proxy filings in Snowflake.
        Returns a plain dict for uniform downstream access.
        Falls back to neutral defaults on any error or when no data found.
        """
        _fallback = {"governance_score": 50.0, "confidence": 0.5}
        try:
            result = self.board_analyzer.analyze_company_governance(ticker)
            if result is None:
                logger.warning(
                    "board_analysis_returned_none",
                    company_id=company_id,
                    ticker=ticker,
                )
                return _fallback
            # GovernanceSignal is a Pydantic model; access attributes directly.
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
        """
        Step 5: Convert CS2 signals + Glassdoor + board dict into EvidenceScore list.
        Skips signals whose 'category' field doesn't map to a known SignalSource.
        """
        evidence_scores: List[EvidenceScore] = []

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
                    raw_value=str(signal.get("id", "")),
                    metadata={"evidence_count": 1},
                )
            )

        # Glassdoor culture signal
        glassdoor_score = Decimal(str(glassdoor.get("overall_score", 50)))
        glassdoor_conf = Decimal(str(glassdoor.get("confidence", 0.5)))
        evidence_scores.append(
            EvidenceScore(
                source=SignalSource.GLASSDOOR_REVIEWS,
                score=glassdoor_score,
                confidence=glassdoor_conf,
                raw_value="glassdoor_overall",
                metadata={"evidence_count": 1},
            )
        )

        # Board composition signal
        board_score = Decimal(str(board.get("governance_score", 50)))
        board_conf = Decimal(str(board.get("confidence", 0.5)))
        evidence_scores.append(
            EvidenceScore(
                source=SignalSource.BOARD_COMPOSITION,
                score=board_score,
                confidence=board_conf,
                raw_value="board_composition",
                metadata={"evidence_count": 1},
            )
        )

        return evidence_scores

    # -----------------------------------------------------------------------
    # Calculation helpers
    # -----------------------------------------------------------------------

    def _calculate_alignment(self, vr_result, hr_result) -> float:
        """
        Alignment = 1.0 - |VR - HR| / 100, clamped to [0.0, 1.0].
        High alignment means company readiness mirrors industry expectations.
        """
        raw = 1.0 - abs(float(vr_result.vr_score) - float(hr_result.hr_score)) / 100.0
        return max(0.0, min(1.0, raw))

    def _inline_synergy(self, vr_result, hr_result, alignment: float) -> Decimal:
        """
        Inline synergy when teammate's SynergyCalculator is unavailable.
        Formula: synergy = (VR * HR / 100) * alignment * 1.0
        Produces a value in [0, 100].
        """
        return (
            vr_result.vr_score * hr_result.hr_score / Decimal("100")
        ) * Decimal(str(alignment)) * Decimal("1.0")

    def _calculate_ci(
        self,
        final_score: Decimal,
        total_evidence: int,
    ):
        """
        Step 11: Calculate confidence interval.
        Delegates to teammate's ConfidenceCalculator when available.
        Falls back to ±5 pt stub with confidence=0.7.

        Returns (ci_lower, ci_upper, confidence) as Decimals, clamped to [0,100].
        """
        if self.ci_calculator is not None:
            try:
                ci_result = self.ci_calculator.calculate(
                    score=final_score,
                    score_type="org_air",
                    evidence_count=total_evidence,
                )
                # Duck-type: try attribute access first, then dict
                try:
                    ci_lower = Decimal(str(ci_result.ci_lower))
                    ci_upper = Decimal(str(ci_result.ci_upper))
                    confidence = Decimal(str(ci_result.confidence))
                except AttributeError:
                    ci_lower = Decimal(str(ci_result["ci_lower"]))
                    ci_upper = Decimal(str(ci_result["ci_upper"]))
                    confidence = Decimal(str(ci_result["confidence"]))
            except Exception as exc:
                logger.warning("confidence_calculator_failed", error=str(exc))
                ci_lower = final_score - Decimal("5")
                ci_upper = final_score + Decimal("5")
                confidence = Decimal("0.7")
        else:
            ci_lower = final_score - Decimal("5")
            ci_upper = final_score + Decimal("5")
            confidence = Decimal("0.7")

        # Clamp to valid range
        ci_lower = max(Decimal("0"), ci_lower)
        ci_upper = min(Decimal("100"), ci_upper)

        return ci_lower, ci_upper, confidence

    # -----------------------------------------------------------------------
    # Persistence
    # -----------------------------------------------------------------------

    def _persist_assessment(self, result: Dict[str, Any]) -> None:
        """
        Step 13: Insert assessment directly into Snowflake.
        Logs on failure but does NOT raise — scoring result is still returned.
        """
        settings = get_settings()
        table = f"{settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.ASSESSMENTS"
        assessment_id = str(uuid4())
        try:
            conn = get_connection()
            cur = conn.cursor()
            try:
                cur.execute(f"""
                    INSERT INTO {table} (id, company_id, assessment_type, status, primary_assessor)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    assessment_id,
                    str(result["company_id"]),
                    "ai_readiness",
                    "completed",
                    "CS3_AutoScorer",
                ))
                conn.commit()
                logger.info(
                    "assessment_persisted",
                    company_id=result["company_id"],
                    ticker=result["ticker"],
                    assessment_id=assessment_id,
                )
            finally:
                cur.close()
                conn.close()
        except Exception as exc:
            logger.error(
                "assessment_persist_failed",
                company_id=result["company_id"],
                ticker=result["ticker"],
                error=str(exc),
            )

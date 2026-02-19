"""
Test Full Scoring Pipeline: Path A + Path B + VR

Tests:
1. Evidence Helpers (all 7 dimensions extract text)
2. Rubric Scorer (all 7 dimensions score from text)
3. Combined scoring (Path A + Path B merge)
4. VR calculation (end-to-end)

Run:
    pytest tests/test_scoring_pipeline.py -v -s
"""

import pytest
from decimal import Decimal
from uuid import UUID
import structlog

from app.services.scoring_service import ScoringService
from app.scoring.evidence_helpers import get_dimension_evidence
from app.scoring.rubric_scorer import RubricScorer
from app.services.snowflake import get_connection
from app.config import get_settings

logger = structlog.get_logger()

DIMENSIONS = [
    "data_infrastructure", "ai_governance", "technology_stack",
    "talent", "leadership", "use_case_portfolio", "culture"
]


def get_test_companies():
    """Fetch first 3 companies from Snowflake for testing."""
    settings = get_settings()
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(f"""
            SELECT c.id, c.ticker, c.name
            FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.companies c
            WHERE c.is_deleted = FALSE
            ORDER BY c.ticker
            LIMIT 3
        """)
        rows = cur.fetchall()
        return [(UUID(r[0]), r[1], r[2]) for r in rows]
    finally:
        cur.close()
        conn.close()


# ============================================================
# TEST 1: Evidence Helpers - do all 7 dimensions return text?
# ============================================================

class TestEvidenceHelpers:

    @pytest.mark.integration
    def test_all_dimensions_extract(self):
        """Verify get_dimension_evidence works for all 7 dimensions."""
        companies = get_test_companies()
        assert companies, "No companies found in database"

        company_id, ticker, name = companies[0]
        print(f"\n{'='*70}")
        print(f"EVIDENCE HELPERS TEST - {ticker} ({name})")
        print(f"{'='*70}")

        results = {}
        for dim in DIMENSIONS:
            text, metrics = get_dimension_evidence(company_id, ticker, dim)
            word_count = len(text.split()) if text else 0
            results[dim] = {"words": word_count, "metrics": metrics}
            print(f"  {dim:25s} | words={word_count:4d} | metrics={list(metrics.keys())}")

        # At least some dimensions should have evidence
        dims_with_data = sum(1 for r in results.values() if r["words"] > 0)
        print(f"\n  Dimensions with evidence: {dims_with_data}/7")
        assert dims_with_data > 0, "No evidence extracted for any dimension"


# ============================================================
# TEST 2: Rubric Scorer - do all 7 dimensions score?
# ============================================================

class TestRubricScorer:

    @pytest.mark.integration
    def test_all_dimensions_score(self):
        """Verify RubricScorer produces scores for all 7 dimensions."""
        companies = get_test_companies()
        assert companies, "No companies found in database"

        company_id, ticker, name = companies[0]
        scorer = RubricScorer()

        print(f"\n{'='*70}")
        print(f"RUBRIC SCORER TEST - {ticker} ({name})")
        print(f"{'='*70}")
        print(f"  {'Dimension':25s} | {'Level':10s} | {'Score':>6s} | {'Keywords':>4s} | Rationale")
        print(f"  {'-'*90}")

        for dim in DIMENSIONS:
            text, metrics = get_dimension_evidence(company_id, ticker, dim)
            result = scorer.score_dimension(dim, text, metrics)

            print(f"  {dim:25s} | {result.level.label:10s} | {result.score:6.1f} | {result.keyword_match_count:4d} | {result.rationale}")

            # Score should be valid
            assert 0 <= result.score <= 100, f"{dim} score {result.score} out of bounds"
            assert result.level is not None
            assert result.rationale


# ============================================================
# TEST 3: Combined Scoring (Path A + Path B)
# ============================================================

class TestCombinedScoring:

    @pytest.mark.integration
    def test_combined_path_a_b(self):
        """Verify ScoringService combines Path A + Path B."""
        companies = get_test_companies()
        assert companies, "No companies found in database"

        company_id, ticker, name = companies[0]
        service = ScoringService()

        print(f"\n{'='*70}")
        print(f"COMBINED SCORING TEST - {ticker} ({name})")
        print(f"{'='*70}")

        result = service.score_company(company_id, include_audit_trail=True)

        # Check metadata
        method = result["metadata"]["scoring_method"]
        path_b = result["metadata"]["path_b_included"]
        rubric_dims = result["metadata"].get("rubric_dimensions_scored", [])

        print(f"  Scoring method : {method}")
        print(f"  Path B included: {path_b}")
        print(f"  Rubric dims    : {rubric_dims}")

        # Print dimension scores
        print(f"\n  {'Dimension':25s} | {'Score':>6s} | Method")
        print(f"  {'-'*55}")
        for dim_name, data in result["dimension_scores"].items():
            print(f"  {dim_name:25s} | {data['score']:6.1f} | {data.get('method', 'n/a')}")

        # Print rubric details if available
        if "audit_trail" in result and "rubric_details" in result["audit_trail"]:
            print(f"\n  RUBRIC DETAILS (Path B):")
            for dim, info in result["audit_trail"]["rubric_details"].items():
                kws = info["matched_keywords"][:5]
                print(f"    {dim:25s} -> {info['level']:10s} (score={info['score']:5.1f}) keywords={kws}")

        assert method == "combined_path_a_b", f"Expected combined method, got {method}"
        assert len(result["dimension_scores"]) == 7


# ============================================================
# TEST 4: VR Calculation (End-to-End)
# ============================================================

class TestVREndToEnd:

    @pytest.mark.integration
    def test_vr_calculation(self):
        """Verify full VR pipeline: Path A + B -> combine -> VR."""
        companies = get_test_companies()
        assert companies, "No companies found in database"

        company_id, ticker, name = companies[0]
        service = ScoringService()

        print(f"\n{'='*70}")
        print(f"VR CALCULATION TEST - {ticker} ({name})")
        print(f"{'='*70}")

        vr = service.calculate_vr(company_id, include_audit_trail=True)

        print(f"  V^R Score       : {vr['vr_score']:.2f}/100")
        print(f"  Sector          : {vr['sector']}")
        print(f"  Base score      : {vr['vr_components']['base_score']:.2f}")
        print(f"  CV penalty      : -{vr['vr_components']['cv_penalty_amount']:.2f}")
        print(f"  TC penalty      : -{vr['vr_components']['tc_penalty_amount']:.2f}")

        print(f"\n  Dimension Scores:")
        for dim, score in vr["dimension_scores"].items():
            print(f"    {dim:25s} : {score:.1f}")

        # VR should be valid
        assert 0 <= vr["vr_score"] <= 100, f"VR score {vr['vr_score']} out of bounds"
        assert vr["sector"] is not None

    @pytest.mark.integration
    def test_vr_multiple_companies(self):
        """Compare VR scores across companies."""
        companies = get_test_companies()
        assert len(companies) >= 2, "Need at least 2 companies"

        service = ScoringService()

        print(f"\n{'='*70}")
        print(f"VR COMPARISON")
        print(f"{'='*70}")
        print(f"  {'Ticker':6s} | {'Name':25s} | {'VR Score':>8s} | {'Sector':20s}")
        print(f"  {'-'*70}")

        vr_scores = []
        for company_id, ticker, name in companies:
            try:
                vr = service.calculate_vr(company_id)
                vr_scores.append(vr["vr_score"])
                print(f"  {ticker:6s} | {name:25s} | {vr['vr_score']:8.2f} | {vr['sector']}")
            except Exception as e:
                print(f"  {ticker:6s} | {name:25s} | {'ERROR':>8s} | {str(e)[:30]}")

        # Scores should differ across companies
        if len(vr_scores) >= 2:
            assert len(set(vr_scores)) > 1, "All companies got identical VR scores"


# ============================================================
# TEST 5: ADP Path A vs Path B Breakdown
# ============================================================

def get_company_by_ticker(ticker: str):
    """Fetch a single company by ticker."""
    settings = get_settings()
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(f"""
            SELECT c.id, c.ticker, c.name
            FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.companies c
            WHERE c.ticker = %s AND c.is_deleted = FALSE
        """, (ticker,))
        row = cur.fetchone()
        if not row:
            return None
        return (UUID(row[0]), row[1], row[2])
    finally:
        cur.close()
        conn.close()


class TestADPPathScores:

    @pytest.mark.integration
    def test_adp_path_a_vs_path_b(self):
        """Show Path A and Path B scores side-by-side for ADP."""
        from app.scoring.evidence_mapper import EvidenceMapper, Dimension, SignalSource, EvidenceScore

        company = get_company_by_ticker("ADP")
        assert company, "ADP not found in database"

        company_id, ticker, name = company
        service = ScoringService()
        scorer = RubricScorer()
        mapper = EvidenceMapper()

        print(f"\n{'='*90}")
        print(f"  ADP ({name}) - PATH A vs PATH B BREAKDOWN")
        print(f"{'='*90}")

        # ── Path A: Evidence Mapper (quantitative) ──
        evidence_scores = service._fetch_external_signals(company_id)
        path_a_scores = mapper.map_evidence_to_dimensions(evidence_scores)

        # ── Path B: Rubric Scorer (qualitative) ──
        path_b_scores = {}
        for dim in DIMENSIONS:
            try:
                text, metrics = get_dimension_evidence(company_id, ticker, dim)
                if text:
                    path_b_scores[dim] = scorer.score_dimension(dim, text, metrics)
            except Exception as e:
                logger.warning("path_b_failed", dimension=dim, error=str(e))

        # -- Print Path A --
        print(f"\n  {'-'*40}")
        print(f"  PATH A - Evidence Mapper (weight: 60%)")
        print(f"  {'-'*40}")
        print(f"  {'Dimension':25s} | {'Score':>7s} | {'Confidence':>10s} | {'Method':15s} | Contributions")
        print(f"  {'-'*90}")
        for dim_enum, ds in path_a_scores.items():
            contribs = ", ".join(
                f"{c.source.value}({float(c.weighted_contribution):.1f})"
                for c in ds.contributions
            )
            print(f"  {dim_enum.value:25s} | {float(ds.score):7.1f} | {float(ds.confidence):10.2f} | {ds.method:15s} | {contribs}")

        # -- Print Path B --
        print(f"\n  {'-'*40}")
        print(f"  PATH B - Rubric Scorer (weight: 40%)")
        print(f"  {'-'*40}")
        print(f"  {'Dimension':25s} | {'Score':>7s} | {'Level':10s} | {'KW Hits':>7s} | Rationale")
        print(f"  {'-'*90}")
        for dim in DIMENSIONS:
            if dim in path_b_scores:
                r = path_b_scores[dim]
                print(f"  {dim:25s} | {float(r.score):7.1f} | {r.level.label:10s} | {r.keyword_match_count:7d} | {r.rationale}")
            else:
                print(f"  {dim:25s} | {'N/A':>7s} | {'--':10s} | {'--':>7s} | no evidence")

        # -- Print Combined (60/40) --
        print(f"\n  {'-'*40}")
        print(f"  COMBINED (0.6 x Path A + 0.4 x Path B)")
        print(f"  {'-'*40}")
        print(f"  {'Dimension':25s} | {'Path A':>7s} | {'Path B':>7s} | {'Combined':>8s}")
        print(f"  {'-'*55}")
        for dim_enum, ds in path_a_scores.items():
            dim_name = dim_enum.value
            path_a_val = float(ds.score)
            if dim_name in path_b_scores:
                path_b_val = float(path_b_scores[dim_name].score)
                combined = round(path_a_val * 0.6 + path_b_val * 0.4, 2)
                print(f"  {dim_name:25s} | {path_a_val:7.1f} | {path_b_val:7.1f} | {combined:8.2f}")
            else:
                print(f"  {dim_name:25s} | {path_a_val:7.1f} | {'N/A':>7s} | {path_a_val:8.2f}")

        print(f"\n{'='*90}\n")

        # Basic assertions
        assert len(path_a_scores) == 7, f"Expected 7 Path A dimensions, got {len(path_a_scores)}"
        assert len(path_b_scores) > 0, "Path B produced no scores for ADP"


# ============================================================
# TEST 6: Property-Based Tests for EvidenceMapper (Hypothesis)
# ============================================================

from hypothesis import given, strategies as st, settings as hyp_settings
from app.scoring.evidence_mapper import EvidenceMapper, EvidenceScore, SignalSource, Dimension

# Strategy: generate a valid EvidenceScore with random source, score, confidence
evidence_score_strategy = st.builds(
    EvidenceScore,
    source=st.sampled_from(list(SignalSource)),
    score=st.decimals(min_value=0, max_value=100, places=2, allow_nan=False, allow_infinity=False),
    confidence=st.decimals(min_value=Decimal("0.01"), max_value=1, places=2, allow_nan=False, allow_infinity=False),
    raw_value=st.just("test"),
)


class TestEvidenceMapperProperties:
    """Property-based tests using Hypothesis — pure unit tests, no DB required."""

    @given(evidence_list=st.lists(evidence_score_strategy, min_size=0, max_size=10))
    @hyp_settings(max_examples=500)
    def test_all_dimensions_returned(self, evidence_list):
        """Mapper must ALWAYS return exactly 7 dimensions, regardless of input."""
        mapper = EvidenceMapper()
        result = mapper.map_evidence_to_dimensions(evidence_list)

        assert len(result) == 7, f"Expected 7 dimensions, got {len(result)}"
        for dim in Dimension:
            assert dim in result, f"Missing dimension: {dim.value}"

    @hyp_settings(max_examples=500)
    @given(st.just([]))
    def test_missing_evidence_defaults_to_50(self, empty_list):
        """With no evidence, ALL 7 dimensions must default to 50.0."""
        mapper = EvidenceMapper()
        result = mapper.map_evidence_to_dimensions(empty_list)

        for dim in Dimension:
            score = float(result[dim].score)
            assert score == 50.0, f"{dim.value} expected 50.0, got {score}"
            assert result[dim].method == "default"

    @given(
        single_source=st.sampled_from(list(SignalSource)),
        multi_sources=st.lists(
            st.sampled_from(list(SignalSource)),
            min_size=3,
            max_size=6,
            unique=True,
        ),
        score=st.decimals(min_value=10, max_value=90, places=2, allow_nan=False, allow_infinity=False),
        confidence=st.decimals(min_value=Decimal("0.5"), max_value=1, places=2, allow_nan=False, allow_infinity=False),
    )
    @hyp_settings(max_examples=500)
    def test_more_evidence_higher_confidence(self, single_source, multi_sources, score, confidence):
        """More evidence sources should produce equal or higher average confidence."""
        mapper = EvidenceMapper()

        # Single source
        single_evidence = [
            EvidenceScore(source=single_source, score=score, confidence=confidence, raw_value="test")
        ]
        result_single = mapper.map_evidence_to_dimensions(single_evidence)

        # Multiple sources
        multi_evidence = [
            EvidenceScore(source=src, score=score, confidence=confidence, raw_value="test")
            for src in multi_sources
        ]
        result_multi = mapper.map_evidence_to_dimensions(multi_evidence)

        # Average confidence across non-default dimensions should be >= with more evidence
        def avg_confidence(result):
            scored = [float(ds.confidence) for ds in result.values() if ds.method != "default"]
            return sum(scored) / len(scored) if scored else 0.5

        conf_single = avg_confidence(result_single)
        conf_multi = avg_confidence(result_multi)

        # Allow tiny floating-point tolerance (1e-9)
        assert conf_multi >= conf_single - 1e-9, (
            f"More evidence ({len(multi_sources)} sources) gave lower confidence "
            f"({conf_multi:.3f}) than single source ({conf_single:.3f})"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

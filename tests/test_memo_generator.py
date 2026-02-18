"""
Test Investment Memo Generator

Tests:
1. Memo generation for ADP (or first available company)
2. Markdown contains required sections
3. JSON summary has recommendation field

Run:
    pytest tests/test_memo_generator.py -v -s
"""

import pytest
from uuid import UUID
import structlog

from app.services.scoring_service import ScoringService
from app.scoring.investment_memo_generator import InvestmentMemoGenerator
from app.services.snowflake import get_connection
from app.config import get_settings

logger = structlog.get_logger()


def get_adp_company():
    """Fetch ADP company from Snowflake. Falls back to first available company."""
    settings = get_settings()
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Try ADP first
        cur.execute(f"""
            SELECT c.id, c.ticker, c.name
            FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.companies c
            WHERE c.ticker = 'ADP' AND c.is_deleted = FALSE
            LIMIT 1
        """)
        row = cur.fetchone()
        if row:
            return UUID(row[0]), row[1], row[2]

        # Fallback to first company
        cur.execute(f"""
            SELECT c.id, c.ticker, c.name
            FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.companies c
            WHERE c.is_deleted = FALSE
            ORDER BY c.ticker
            LIMIT 1
        """)
        row = cur.fetchone()
        if row:
            return UUID(row[0]), row[1], row[2]
        pytest.skip("No companies found in database")
    finally:
        cur.close()
        conn.close()


REQUIRED_SECTIONS = [
    "Executive Summary",
    "Path A vs Path B",
    "Risk",
    "Opportunit",
]


class TestInvestmentMemoGenerator:

    @pytest.mark.integration
    def test_memo_generation(self):
        """Generate a full memo and verify structure."""
        company_id, ticker, name = get_adp_company()
        logger.info("test_memo_target", ticker=ticker, company_id=str(company_id))

        # Score the company (combined Path A + B)
        service = ScoringService()
        dimension_result = service.score_company(company_id, include_audit_trail=True)
        vr_result = service.calculate_vr(company_id)

        # Extract Path A / Path B scores
        path_a_scores = {}
        path_b_scores = {}
        audit = dimension_result.get("audit_trail", {})
        rubric_details = audit.get("rubric_details", {})

        for dim_name, dim_data in dimension_result["dimension_scores"].items():
            path_a_scores[dim_name] = dim_data["score"]
            if dim_name in rubric_details:
                path_b_scores[dim_name] = rubric_details[dim_name]

        # Generate memo
        generator = InvestmentMemoGenerator()
        markdown, summary = generator.generate_memo(
            ticker=ticker,
            company_name=name,
            path_a_scores=path_a_scores,
            path_b_scores=path_b_scores,
            vr_result=vr_result,
        )

        # ── Assertions ──
        assert markdown, "Markdown should not be empty"
        assert len(markdown) > 200, f"Markdown too short ({len(markdown)} chars)"

        # Check required sections (case-insensitive substring match)
        md_lower = markdown.lower()
        for section in REQUIRED_SECTIONS:
            assert section.lower() in md_lower, (
                f"Missing section '{section}' in memo"
            )

        # Check JSON summary
        assert "recommendation" in summary, "Summary must have 'recommendation'"
        assert summary["recommendation"] in ("BUY", "HOLD", "PASS"), (
            f"Invalid recommendation: {summary['recommendation']}"
        )
        assert "vr_score" in summary, "Summary must have 'vr_score'"

        # Log results
        logger.info(
            "memo_test_passed",
            ticker=ticker,
            recommendation=summary["recommendation"],
            vr_score=summary.get("vr_score"),
            markdown_length=len(markdown),
        )
        print(f"\n{'='*60}")
        print(f"MEMO for {name} ({ticker})")
        print(f"Recommendation: {summary['recommendation']}")
        print(f"V^R Score: {summary.get('vr_score')}")
        print(f"Top Strength: {summary.get('top_strength')}")
        print(f"Top Weakness: {summary.get('top_weakness')}")
        print(f"Discrepancies: {summary.get('discrepancy_flags')}")
        print(f"{'='*60}")
        print(markdown[:2000].encode("ascii", errors="replace").decode("ascii"))

    @pytest.mark.integration
    def test_fallback_memo(self):
        """Verify fallback memo works when API key is missing."""
        generator = InvestmentMemoGenerator()

        path_a = {
            "data_infrastructure": 45.0,
            "ai_governance": 30.0,
            "technology_stack": 55.0,
            "talent": 60.0,
            "leadership": 40.0,
            "use_case_portfolio": 35.0,
            "culture": 50.0,
        }
        path_b = {
            "talent": {"score": 70.0, "level": "Good"},
            "leadership": {"score": 20.0, "level": "Developing"},
        }
        vr_result = {
            "vr_score": 38.5,
            "sector": "technology",
            "vr_components": {
                "base_score": 45.0,
                "cv": 0.3,
                "cv_penalty": 0.925,
                "cv_penalty_amount": 3.4,
                "talent_concentration": 0.2,
                "talent_risk_adj": 1.0,
                "tc_penalty_amount": 0.0,
            },
            "dimension_scores": path_a,
        }

        markdown, summary = generator._fallback_memo(
            ticker="TEST",
            company_name="Test Corp",
            path_a_scores=path_a,
            path_b_scores=path_b,
            vr_result=vr_result,
        )

        assert "HOLD" in markdown or "Test Corp" in markdown
        assert summary["recommendation"] == "HOLD"
        assert summary["vr_score"] == 38.5
        assert summary.get("fallback") is True
        # Leadership has |40 - 20| = 20 > 15
        assert "leadership" in summary["discrepancy_flags"]

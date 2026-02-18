"""
Unit tests for RubricScorer (Path B).

No Snowflake connection required — all tests use synthetic evidence text
and quantitative metrics injected directly.

Run:
    pytest tests/unit/test_rubric_scorer.py -v
"""

import pytest
from decimal import Decimal

from app.scoring.rubric_scorer import RubricScorer, RubricResult, ScoreLevel


@pytest.fixture
def scorer():
    return RubricScorer()


# ── helpers ──────────────────────────────────────────────────────────────────

def _assert_valid_result(result: RubricResult, dimension: str):
    assert isinstance(result, RubricResult)
    assert result.dimension == dimension
    assert result.level is not None
    assert Decimal("0") <= result.score <= Decimal("100")
    assert Decimal("0") <= result.confidence <= Decimal("1")
    assert result.rationale


# ── score_dimension dispatch ─────────────────────────────────────────────────

class TestScoreDimensionDispatch:

    def test_all_seven_dimensions_dispatch(self, scorer):
        """Every known dimension key must return a valid RubricResult."""
        dimensions = [
            "data_infrastructure",
            "ai_governance",
            "technology_stack",
            "talent_skills",
            "leadership_vision",
            "use_case_portfolio",
            "culture",
        ]
        for dim in dimensions:
            result = scorer.score_dimension(dim, "some evidence text", {})
            _assert_valid_result(result, dim)

    def test_unknown_dimension_returns_default(self, scorer):
        result = scorer.score_dimension("nonexistent_dim", "text", {})
        assert result.dimension == "nonexistent_dim"
        assert result.score == Decimal("50.0")
        assert result.confidence == Decimal("0.5")
        assert "not recognized" in result.rationale

    def test_empty_evidence_does_not_raise(self, scorer):
        for dim in ["data_infrastructure", "ai_governance", "technology_stack",
                    "talent_skills", "leadership_vision", "use_case_portfolio", "culture"]:
            result = scorer.score_dimension(dim, "", {})
            _assert_valid_result(result, dim)


# ── data_infrastructure ──────────────────────────────────────────────────────

class TestDataInfrastructure:

    def test_level_5_keywords(self, scorer):
        text = "snowflake databricks lakehouse real-time api-first data mesh streaming"
        result = scorer.score_dimension(
            "data_infrastructure", text,
            {"data_quality_score": 0.70}
        )
        assert result.level == ScoreLevel.LEVEL_5
        assert result.score >= Decimal("80")

    def test_level_4_keywords(self, scorer):
        text = "azure aws data lake etl batch pipelines redshift"
        result = scorer.score_dimension(
            "data_infrastructure", text,
            {"data_quality_score": 0.35}
        )
        assert result.level == ScoreLevel.LEVEL_4

    def test_level_1_keywords(self, scorer):
        text = "mainframe spreadsheets manual processes excel-based"
        result = scorer.score_dimension("data_infrastructure", text, {})
        assert result.level == ScoreLevel.LEVEL_1
        assert result.score <= Decimal("20")

    def test_confidence_bonus_for_many_keywords(self, scorer):
        text = "snowflake databricks lakehouse real-time api-first data mesh streaming event-driven microservices"
        result = scorer.score_dimension(
            "data_infrastructure", text,
            {"data_quality_score": 0.80}
        )
        assert result.confidence >= Decimal("0.90")

    def test_quantitative_threshold_blocks_level_5(self, scorer):
        """Good keywords but failing quantitative threshold → should not reach Level 5."""
        text = "snowflake databricks lakehouse real-time api-first data mesh streaming"
        result = scorer.score_dimension(
            "data_infrastructure", text,
            {"data_quality_score": 0.10}  # below 0.60 threshold
        )
        assert result.level != ScoreLevel.LEVEL_5


# ── ai_governance ────────────────────────────────────────────────────────────

class TestAIGovernance:

    def test_level_5_chief_ai_officer(self, scorer):
        text = "caio chief ai officer board committee model risk ai ethics board responsible ai"
        result = scorer.score_dimension("ai_governance", text, {})
        assert result.level == ScoreLevel.LEVEL_5

    def test_level_3_committee_mention(self, scorer):
        text = "director guidelines governance committee"
        result = scorer.score_dimension("ai_governance", text, {})
        assert result.level in (ScoreLevel.LEVEL_3, ScoreLevel.LEVEL_4)

    def test_level_1_no_oversight(self, scorer):
        text = "no governance no oversight unmanaged risk"
        result = scorer.score_dimension("ai_governance", text, {})
        assert result.level == ScoreLevel.LEVEL_1


# ── technology_stack ─────────────────────────────────────────────────────────

class TestTechnologyStack:

    def test_level_5_mlops(self, scorer):
        text = "sagemaker mlops feature store model registry automated pipelines kubeflow"
        result = scorer.score_dimension(
            "technology_stack", text,
            {"mlops_maturity": 0.70}
        )
        assert result.level == ScoreLevel.LEVEL_5

    def test_level_3_notebooks(self, scorer):
        text = "jupyter notebooks python machine learning deep learning"
        result = scorer.score_dimension(
            "technology_stack", text,
            {"mlops_maturity": 0.20}
        )
        assert result.level == ScoreLevel.LEVEL_3

    def test_level_2_excel_no_ml(self, scorer):
        text = "excel tableau only no ml manual analysis"
        result = scorer.score_dimension("technology_stack", text, {})
        assert result.level == ScoreLevel.LEVEL_2


# ── talent_skills ────────────────────────────────────────────────────────────

class TestTalentSkills:

    def test_level_5_research_team(self, scorer):
        text = "ml platform ai research principal engineer staff engineer low turnover pytorch transformers"
        result = scorer.score_dimension(
            "talent_skills", text,
            {"ai_job_ratio": 0.50}
        )
        assert result.level == ScoreLevel.LEVEL_5

    def test_level_3_small_team(self, scorer):
        text = "data scientist growing team sql aws cloud"
        result = scorer.score_dimension(
            "talent_skills", text,
            {"ai_job_ratio": 0.16}
        )
        assert result.level == ScoreLevel.LEVEL_3

    def test_level_1_no_talent(self, scorer):
        text = "no data scientist vendor only outsourced consultants only"
        result = scorer.score_dimension("talent_skills", text, {})
        assert result.level == ScoreLevel.LEVEL_1

    def test_dimension_key_matches_enum(self, scorer):
        """Ensure 'talent_skills' is correctly dispatched (not old 'talent' key)."""
        result = scorer.score_dimension("talent_skills", "data scientist ml engineer python", {})
        assert result.dimension == "talent_skills"
        assert result.level is not None


# ── leadership_vision ────────────────────────────────────────────────────────

class TestLeadershipVision:

    def test_level_5_ceo_board_ai(self, scorer):
        text = "ceo ai board committee ai strategy ceo publicly champions board ai committee"
        result = scorer.score_dimension(
            "leadership_vision", text,
            {"leadership_score": 0.60}
        )
        assert result.level == ScoreLevel.LEVEL_5

    def test_level_4_cto_strategic_priority(self, scorer):
        text = "cto ai strategic priority chief technology officer executive engagement"
        result = scorer.score_dimension(
            "leadership_vision", text,
            {"leadership_score": 0.30}
        )
        assert result.level == ScoreLevel.LEVEL_4

    def test_ai_executive_count_boosts_confidence(self, scorer):
        text = "chief technology officer chief data officer chief ai officer"
        result = scorer.score_dimension(
            "leadership_vision", text,
            {"leadership_score": 0.40, "ai_executive_count": 3}
        )
        assert result.confidence >= Decimal("0.85")

    def test_dimension_key_matches_enum(self, scorer):
        """Ensure 'leadership_vision' is correctly dispatched (not old 'leadership' key)."""
        result = scorer.score_dimension("leadership_vision", "ceo ai board committee ai strategy", {})
        assert result.dimension == "leadership_vision"


# ── use_case_portfolio ───────────────────────────────────────────────────────

class TestUseCasePortfolio:

    def test_level_5_production_roi(self, scorer):
        text = "production ai 3x roi ai product documented roi revenue-generating deployed models"
        result = scorer.score_dimension(
            "use_case_portfolio", text,
            {"production_use_cases": 6.0}
        )
        assert result.level == ScoreLevel.LEVEL_5

    def test_level_3_pilot(self, scorer):
        text = "pilot early production machine learning analytics intelligent"
        result = scorer.score_dimension(
            "use_case_portfolio", text,
            {"production_use_cases": 1.0}
        )
        assert result.level == ScoreLevel.LEVEL_3

    def test_level_2_poc_only(self, scorer):
        text = "proof of concept poc experiments prototype"
        result = scorer.score_dimension("use_case_portfolio", text, {})
        assert result.level == ScoreLevel.LEVEL_2


# ── culture ──────────────────────────────────────────────────────────────────

class TestCulture:

    def test_level_5_innovation_driven(self, scorer):
        text = "innovative data-driven fail-fast experimentation culture agile iterative cutting-edge rewarded"
        result = scorer.score_dimension("culture", text, {})
        assert result.level == ScoreLevel.LEVEL_5

    def test_level_2_resistant(self, scorer):
        text = "bureaucratic resistant change resistant hierarchical traditional"
        result = scorer.score_dimension("culture", text, {})
        assert result.level == ScoreLevel.LEVEL_2

    def test_level_1_hostile(self, scorer):
        text = "hostile to change no data culture no innovation siloed"
        result = scorer.score_dimension("culture", text, {})
        assert result.level == ScoreLevel.LEVEL_1


# ── score interpolation ──────────────────────────────────────────────────────

class TestScoreInterpolation:

    def test_score_within_level_bounds(self, scorer):
        """Interpolated score must always fall within the level's min/max range."""
        text = "snowflake databricks lakehouse real-time api-first data mesh"
        result = scorer.score_dimension(
            "data_infrastructure", text,
            {"data_quality_score": 0.70}
        )
        assert result.level.min_score <= result.score <= result.level.max_score

    def test_more_keywords_higher_score_within_level(self, scorer):
        """More keyword matches should produce a higher interpolated score."""
        few_kw = "azure aws"
        many_kw = "azure aws gcp warehouse etl batch pipelines hybrid cloud data catalog cloud data data lake"
        r_few = scorer.score_dimension("data_infrastructure", few_kw, {"data_quality_score": 0.35})
        r_many = scorer.score_dimension("data_infrastructure", many_kw, {"data_quality_score": 0.35})
        if r_few.level == r_many.level:
            assert r_many.score >= r_few.score


# ── fallback: no criteria met ────────────────────────────────────────────────

class TestFallback:

    def test_no_keywords_returns_level_1_default(self, scorer):
        """Completely unrelated text → falls to bottom sentinel."""
        text = "the quick brown fox jumps over the lazy dog"
        result = scorer.score_dimension("data_infrastructure", text, {})
        assert result.level == ScoreLevel.LEVEL_1
        assert result.keyword_match_count == 0
        assert result.score == Decimal("10.0")

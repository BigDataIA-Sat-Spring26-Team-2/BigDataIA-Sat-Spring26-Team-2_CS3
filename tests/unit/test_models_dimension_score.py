import pytest
from uuid import uuid4
from pydantic import ValidationError

from app.models.dimension import DimensionScoreCreate
from app.models.enums import Dimension


def test_dimension_score_default_weight():
    s = DimensionScoreCreate(
        assessment_id=uuid4(),
        dimension=Dimension.DATA_INFRASTRUCTURE,
        score=80,
        weight=None,
        confidence=0.9,
        evidence_count=2,
    )
    assert s.weight is not None
    assert 0 <= s.weight <= 1


def test_dimension_score_score_range():
    with pytest.raises(ValidationError):
        DimensionScoreCreate(
            assessment_id=uuid4(),
            dimension=Dimension.DATA_INFRASTRUCTURE,
            score=101,
            weight=None,
            confidence=0.9,
            evidence_count=1,
        )


def test_dimension_score_confidence_range():
    with pytest.raises(ValidationError):
        DimensionScoreCreate(
            assessment_id=uuid4(),
            dimension=Dimension.DATA_INFRASTRUCTURE,
            score=80,
            weight=0.2,
            confidence=2.0,
            evidence_count=1,
        )


def test_dimension_score_evidence_non_negative():
    with pytest.raises(ValidationError):
        DimensionScoreCreate(
            assessment_id=uuid4(),
            dimension=Dimension.DATA_INFRASTRUCTURE,
            score=80,
            weight=0.2,
            confidence=0.8,
            evidence_count=-1,
        )

import pytest
from uuid import uuid4
from pydantic import ValidationError
from datetime import datetime, timezone

from app.models.assessment import AssessmentResponse
from app.models.enums import AssessmentType, AssessmentStatus


def test_confidence_interval_invalid():
    with pytest.raises(ValidationError):
        AssessmentResponse(
            id=uuid4(),
            company_id=uuid4(),
            assessment_type=AssessmentType.SCREENING,
            assessment_date=datetime.now(timezone.utc),
            primary_assessor="A",
            secondary_assessor=None,
            status=AssessmentStatus.DRAFT,
            v_r_score=None,
            confidence_lower=90,
            confidence_upper=10,   # invalid
            created_at=datetime.now(timezone.utc),
        )

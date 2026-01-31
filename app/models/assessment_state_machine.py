from typing import Dict, Set
from app.models.enums import AssessmentStatus


def build_allowed_transitions() -> Dict[AssessmentStatus, Set[AssessmentStatus]]:
    return {
        AssessmentStatus.DRAFT: {AssessmentStatus.IN_PROGRESS},
        AssessmentStatus.IN_PROGRESS: {AssessmentStatus.SUBMITTED},
        AssessmentStatus.SUBMITTED: {
            AssessmentStatus.APPROVED,
            AssessmentStatus.SUPERSEDED,
        },
        AssessmentStatus.APPROVED: {AssessmentStatus.SUPERSEDED},
        AssessmentStatus.SUPERSEDED: set(),
    }

from fastapi import APIRouter, HTTPException, status
from typing import List
from uuid import UUID, uuid4
from datetime import datetime, timezone

from app.models.dimension import DimensionScoreCreate, DimensionScoreResponse

router = APIRouter(tags=["Dimension Scores"])


@router.post(
    "/assessments/{assessment_id}/scores",
    response_model=List[DimensionScoreResponse],
    status_code=status.HTTP_201_CREATED
)
def add_dimension_scores(assessment_id: UUID, scores: List[DimensionScoreCreate]):
    created_scores: List[DimensionScoreResponse] = []

    for score in scores:
        # ✅ keep this check since your model includes assessment_id
        if score.assessment_id != assessment_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="assessment_id in body must match path parameter"
            )

        # ✅ use real UUID per score
        created_scores.append(
            DimensionScoreResponse(
                id=uuid4(),
                assessment_id=assessment_id,
                dimension=score.dimension,
                score=score.score,
                weight=score.weight,  # weight auto-filled by model validator if None
                confidence=score.confidence,
                evidence_count=score.evidence_count,
                created_at=datetime.now(timezone.utc)
            )
        )

    return created_scores


@router.get(
    "/assessments/{assessment_id}/scores",
    response_model=List[DimensionScoreResponse]
)
def get_dimension_scores(assessment_id: UUID):
    # Stub for now
    return []


@router.put(
    "/scores/{score_id}",
    response_model=DimensionScoreResponse
)
def update_dimension_score(score_id: UUID, score: DimensionScoreCreate):
    return DimensionScoreResponse(
        id=score_id,
        assessment_id=score.assessment_id,
        dimension=score.dimension,
        score=score.score,
        weight=score.weight,
        confidence=score.confidence,
        evidence_count=score.evidence_count,
        created_at=datetime.now(timezone.utc)
    )

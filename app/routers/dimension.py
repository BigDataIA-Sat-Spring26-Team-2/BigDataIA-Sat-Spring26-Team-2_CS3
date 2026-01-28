from fastapi import APIRouter, HTTPException, status
from typing import List
from uuid import UUID
from datetime import datetime, timezone

from app.models.dimension import (
    DimensionScoreCreate,
    DimensionScoreResponse
)

router = APIRouter(
    tags=["Dimension Scores"]
)

# weight autocaculated if no weight provided else use provided weight until below 1.0 or above 0.0
@router.post(
    "/assessments/{assessment_id}/scores",
    response_model=List[DimensionScoreResponse],
    status_code=status.HTTP_201_CREATED
)
def add_dimension_scores(
    assessment_id: UUID,
    scores: List[DimensionScoreCreate]
):
    created_scores = []

    for score in scores:
       
        if score.assessment_id != assessment_id:
            raise HTTPException(
                status_code=400,
                detail="assessment_id in body must match path parameter"
            )

        created_scores.append(
            DimensionScoreResponse(
                id=UUID(int=0),  
                assessment_id=assessment_id,
                dimension=score.dimension,
                score=score.score,
                weight=score.weight,
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
    
    return []


@router.put(
    "/scores/{score_id}",
    response_model=DimensionScoreResponse
)
def update_dimension_score(
    score_id: UUID,
    score: DimensionScoreCreate
):
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

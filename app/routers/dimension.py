# app/routers/dimension_scores.py
from fastapi import APIRouter, HTTPException, status
from typing import List
from uuid import UUID

from app.models.dimension import DimensionScoreCreate, DimensionScoreResponse
from app.services import dimension_scores_service

router = APIRouter(tags=["Dimension Scores"])


@router.post(
    "/assessments/{assessment_id}/scores",
    response_model=List[DimensionScoreResponse],
    status_code=status.HTTP_201_CREATED
)
def add_dimension_scores(assessment_id: UUID, scores: List[DimensionScoreCreate]):
    return dimension_scores_service.add_dimension_scores(assessment_id, scores)


@router.get(
    "/assessments/{assessment_id}/scores",
    response_model=List[DimensionScoreResponse]
)
def get_dimension_scores(assessment_id: UUID):
    return dimension_scores_service.get_dimension_scores(assessment_id)


@router.put(
    "/scores/{score_id}",
    response_model=DimensionScoreResponse
)
def update_dimension_score(score_id: UUID, score: DimensionScoreCreate):
    return dimension_scores_service.update_dimension_score(score_id, score)

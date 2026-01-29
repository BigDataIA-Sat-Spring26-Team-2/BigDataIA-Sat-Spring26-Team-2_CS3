# app/routers/dimension_scores.py
from fastapi import APIRouter, HTTPException, status
from typing import List
from uuid import UUID

from app.models.dimension import DimensionScoreCreate, DimensionScoreResponse, DimensionWeightsResponse
from app.services import dimension_scores_service

router = APIRouter(tags=["Dimension Scores"])


@router.post(
    "/{assessment_id}/scores",
    response_model=List[DimensionScoreResponse],
    status_code=status.HTTP_201_CREATED
)
def add_dimension_scores(assessment_id: UUID, scores: List[DimensionScoreCreate]):
 
    return dimension_scores_service.add_dimension_scores(assessment_id, scores)


@router.get(
    "/{assessment_id}/scores",
    response_model=List[DimensionScoreResponse]
)
def get_dimension_scores(assessment_id: UUID):

    return dimension_scores_service.get_dimension_scores(assessment_id)


@router.put(
    "/scores/{score_id}",
    response_model=DimensionScoreResponse
)
def update_dimension_score(score_id: UUID, score: DimensionScoreCreate):
    print("🔥 ROUTER HIT: update_dimension_score", flush=True)
    return dimension_scores_service.update_dimension_score(score_id, score)
@router.get(
    "/dimension-weights",
    response_model=DimensionWeightsResponse
)
def get_dimension_weights():
    return dimension_scores_service.get_dimension_weights()
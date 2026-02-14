# app/routers/dimension_scores.py

from fastapi import APIRouter, status, Query
from typing import List
from uuid import UUID

from app.models.dimension import DimensionScoreCreate, DimensionScoreResponse
from app.models.pagination import PaginatedResponse

from app.models.dimension import DimensionScoreCreate, DimensionScoreResponse, DimensionWeightsResponse
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
    response_model=PaginatedResponse[DimensionScoreResponse]
)
def list_dimension_scores(
    assessment_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    return dimension_scores_service.list_dimension_scores(
        assessment_id=assessment_id,
        page=page,
        page_size=page_size,
    )


@router.put(
    "/scores/{score_id}",
    response_model=DimensionScoreResponse
)
def update_dimension_score(score_id: UUID, score: DimensionScoreCreate):

    return dimension_scores_service.update_dimension_score(score_id, score)

  
@router.get(
    "/dimension-weights",
    response_model=DimensionWeightsResponse
)
def get_dimension_weights():
    return dimension_scores_service.get_dimension_weights()

@router.get("/companies/{company_id}/dimension-scores-preview")
def preview_dimension_scores(company_id: UUID):
    """Preview dimension scores from evidence mapper (before storing)"""
    from app.scoring.evidence_mapper import EvidenceMapper
    from app.services.snowflake import get_connection
    from app.config import get_settings
    
    # Get ticker
    settings = get_settings()
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        cur.execute(f"""
            SELECT ticker FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.companies
            WHERE id = %s
        """, (str(company_id),))
        row = cur.fetchone()
        ticker = row[0] if row else "UNKNOWN"
    finally:
        cur.close()
        conn.close()
    
    mapper = EvidenceMapper()
    dimension_scores = mapper.fetch_and_map_company_evidence(str(company_id), ticker)
    
    return {
        "company_id": str(company_id),
        "ticker": ticker,
        "dimensions": {
            d.value: {
                "score": float(s.score),
                "confidence": float(s.confidence),
                "method": s.method,
                "contributions": [
                    {
                        "source": c.source.value,
                        "is_primary": c.is_primary,
                        "weight": float(c.weight),
                        "score": float(c.signal_score)
                    }
                    for c in s.contributions
                ]
            }
            for d, s in dimension_scores.items()
        }
    }

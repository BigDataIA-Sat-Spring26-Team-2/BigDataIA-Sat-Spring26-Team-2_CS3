"""
app/routers/scoring.py

Updated API endpoints using the ScoringService for company-wise scoring.
"""

from fastapi import APIRouter, Query, HTTPException, status
from uuid import UUID
from typing import List, Optional
import structlog

from app.services.scoring_service import ScoringService
from app.scoring.evidence_mapper import Dimension

router = APIRouter(prefix="/scoring", tags=["Scoring"])
logger = structlog.get_logger()

# Initialize service
scoring_service = ScoringService()


@router.get(
    "/companies/{company_id}/dimensions",
    summary="Calculate dimension scores for a company"
)
async def score_company(
    company_id: UUID,
    include_audit_trail: bool = Query(
        False, 
        description="Include detailed calculation breakdown"
    )
):
    """
    Calculate all 7 dimension scores for a specific company.
    
    **Data Flow:**
    1. Fetch external signals from Snowflake WHERE company_id = {company_id}
    2. Run Evidence Mapper (PATH A quantitative scoring)
    3. Return dimension scores
    
    **Example:**
    ```
    GET /scoring/companies/550e8400-e29b-41d4-a716-446655440000/dimensions
    
    Returns:
    {
        "company_id": "550e8400-...",
        "ticker": "CAT",
        "company_name": "Caterpillar Inc.",
        "dimension_scores": {
            "data_infrastructure": {"score": 36.9, "confidence": 0.72, ...},
            "technology_stack": {"score": 54.3, ...},
            ...
        }
    }
    ```
    """
    try:
        result = scoring_service.score_company(
            company_id=company_id,
            include_audit_trail=include_audit_trail
        )
        return result
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            "scoring_endpoint_error",
            company_id=str(company_id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scoring failed: {str(e)}"
        )


@router.get(
    "/companies/{company_id}/dimensions/explain",
    summary="Get human-readable calculation explanations"
)
async def explain_company_scores(company_id: UUID):
    """
    Get detailed explanations of how each dimension was calculated.
    
    Returns plain English descriptions like:
    "data_infrastructure = digital_presence(0.0) × 0.60 + innovation_activity(80.0) × 0.20 + ... = 36.9/100"
    """
    try:
        result = scoring_service.score_company(
            company_id=company_id,
            include_audit_trail=True
        )
        return result["audit_trail"]["explanations"]
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post(
    "/companies/batch",
    summary="Score multiple companies"
)
async def score_multiple_companies(
    company_ids: List[UUID]
):
    """
    Score multiple companies in a single request.
    
    **Request Body:**
    ```json
    {
        "company_ids": [
            "550e8400-e29b-41d4-a716-446655440000",
            "660e8400-e29b-41d4-a716-446655440001"
        ]
    }
    ```
    """
    try:
        results = scoring_service.score_multiple_companies(company_ids)
        return {
            "count": len(results),
            "results": results
        }
    except Exception as e:
        logger.error("batch_scoring_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch scoring failed: {str(e)}"
        )


@router.post(
    "/companies/compare",
    summary="Compare dimension scores across companies"
)
async def compare_companies(
    company_ids: List[UUID],
    dimensions: Optional[List[str]] = Query(
        None,
        description="Specific dimensions to compare (default: all 7)"
    )
):
    """
    Score multiple companies and return comparison table.
    
    **Example Response:**
    ```json
    {
        "dimensions": ["data_infrastructure", "talent", ...],
        "companies": {
            "CAT": {
                "company_id": "...",
                "company_name": "Caterpillar Inc.",
                "scores": {
                    "data_infrastructure": 36.9,
                    "talent": 53.4,
                    ...
                }
            },
            "UNH": {
                "scores": {...}
            }
        }
    }
    ```
    """
    try:
        # Convert dimension strings to Enum if provided
        dimension_enums = None
        if dimensions:
            dimension_enums = [Dimension(d) for d in dimensions]
        
        comparison = scoring_service.compare_companies(
            company_ids=company_ids,
            dimensions=dimension_enums
        )
        return comparison
    
    except Exception as e:
        logger.error("comparison_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Comparison failed: {str(e)}"
        )


@router.get(
    "/health",
    summary="Check scoring service health"
)
async def scoring_health():
    """Check if scoring service and dependencies are working"""
    try:
        # Try to initialize mapper
        from app.scoring.evidence_mapper import EvidenceMapper
        mapper = EvidenceMapper()
        
        return {
            "status": "healthy",
            "components": {
                "evidence_mapper": "ok",
                "snowflake_connection": "ok"
            }
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }
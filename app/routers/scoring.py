"""
app/routers/scoring.py

Updated API endpoints using the ScoringService for company-wise scoring.
"""

from fastapi import APIRouter, Query, HTTPException, status
from uuid import UUID
from typing import Any, Dict, List, Optional
import structlog

from app.services.scoring_service import ScoringService
from app.services.integration_service import ScoringIntegrationService
from app.services.s3_storage import upload_memo_to_s3
from app.scoring.evidence_mapper import Dimension
from app.scoring.investment_memo_generator import InvestmentMemoGenerator

router = APIRouter(prefix="/scoring", tags=["Scoring"])
logger = structlog.get_logger()

# Initialize services
scoring_service = ScoringService()
integration_service = ScoringIntegrationService()
memo_generator = InvestmentMemoGenerator()


def _get_ticker(company_id: UUID) -> str:
    """Look up a company's ticker symbol from Snowflake by company_id."""
    from app.services.snowflake import get_connection
    from app.config import get_settings
    settings = get_settings()
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(f"""
            SELECT ticker FROM {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}.companies
            WHERE id = %s AND is_deleted = FALSE
        """, (str(company_id),))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Company {company_id} not found")
        return row[0]
    finally:
        cur.close()
        conn.close()

@router.get(
    "/companies/{company_id}/vr",
    summary="Calculate V^R (Venture Readiness) score",
    response_model=Dict[str, Any]
)
async def calculate_vr_score(
    company_id: UUID,
    include_audit_trail: bool = Query(
        False,
        description="Include detailed calculation breakdown and formula steps"
    )
):
    """
    Calculate V^R (Venture Readiness) score for a specific company.
    
    **V^R Formula (from Case Study 1, Equation 1):**
    ```
    V^R = D̄_w × (1 - 0.25 × CV) × (1 - 0.15 × max(0, TC - 0.25))
    
    Where:
    - D̄_w = Weighted mean of 7 dimension scores (sector-specific weights)
    - CV = Coefficient of variation (imbalance penalty)
    - TC = Talent concentration (key-person risk)
    ```
    
    **Data Sources:**
    - Dimension scores: From Evidence Mapper (Path A quantitative)
    - TC: Calculated from job posting metadata
    - Sector: From companies table
    
    **Possible Errors:**
    - 400: Missing required data
      - No dimension scores (run dimension scorer first)
      - No job metadata (run job collector first)
      - NULL sector (update companies table)
      - Invalid sector name
    - 404: Company not found
    - 500: Calculation error
    
    **Example Response:**
    ```json
    {
        "company_id": "c1a3b2f4-1111-4a8c-9c01-000000000001",
        "ticker": "CAT",
        "company_name": "Caterpillar Inc.",
        "vr_score": 29.1,
        "vr_components": {
            "base_score": 35.79,
            "cv": 0.749,
            "cv_penalty": 0.813,
            "cv_penalty_amount": 6.71,
            "talent_concentration": 0.15,
            "talent_risk_adj": 1.0,
            "tc_penalty_amount": 0.0
        },
        "dimension_scores": {
            "data_infrastructure": 35.2,
            "talent": 53.4,
            ...
        },
        "sector": "manufacturing"
    }
    ```
    """
    try:
        result = scoring_service.calculate_vr(
            company_id=company_id,
            include_audit_trail=include_audit_trail
        )
        return result
    
    except ValueError as e:
        # Explicit error for missing/invalid data
        logger.error(
            "vr_calculation_data_error",
            company_id=str(company_id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)  # Return exact error message showing what's missing
        )
    
    except KeyError as e:
        # Missing expected data field
        logger.error(
            "vr_calculation_missing_field",
            company_id=str(company_id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required field: {str(e)}"
        )
    
    except Exception as e:
        # Unexpected errors
        logger.error(
            "vr_calculation_unexpected_error",
            company_id=str(company_id),
            error=str(e),
            error_type=type(e).__name__
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"V^R calculation failed: {type(e).__name__}: {str(e)}"
        )


@router.post(
    "/companies/vr/batch",
    summary="Calculate V^R for multiple companies",
    response_model=Dict[str, Any]
)
async def calculate_vr_batch(
    company_ids: List[UUID]
):
    """
    Calculate V^R scores for multiple companies in one request.
    
    Useful for portfolio analysis.
    
    **Request Body:**
    ```json
    {
        "company_ids": [
            "c1a3b2f4-1111-4a8c-9c01-000000000001",
            "31715ac6-8556-4f84-89f5-1de9b847ff19",
            "c52e8f9d-09a2-4bbc-8c75-a5d3b6834fcf"
        ]
    }
    ```
    
    **Response:**
    ```json
    {
        "count": 3,
        "results": {
            "c1a3b2f4-...": {
                "status": "success",
                "data": { "vr_score": 29.1, ... }
            },
            "31715ac6-...": {
                "status": "failed",
                "error": "No job metadata found..."
            }
        }
    }
    ```
    """
    try:
        results = {}
        
        for company_id in company_ids:
            try:
                result = scoring_service.calculate_vr(company_id)
                results[str(company_id)] = {
                    "status": "success",
                    "data": result
                }
            except Exception as e:
                logger.error(
                    "vr_batch_item_failed",
                    company_id=str(company_id),
                    error=str(e)
                )
                results[str(company_id)] = {
                    "status": "failed",
                    "error": str(e),
                    "error_type": type(e).__name__
                }
        
        # Count successes vs failures
        successful = sum(1 for r in results.values() if r["status"] == "success")
        failed = len(results) - successful
        
        return {
            "total": len(results),
            "successful": successful,
            "failed": failed,
            "results": results
        }
    
    except Exception as e:
        logger.error("vr_batch_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch V^R calculation failed: {str(e)}"
        )


@router.post(
    "/companies/vr/compare",
    summary="Compare V^R scores across companies",
    response_model=Dict[str, Any]
)
async def compare_vr_scores(
    company_ids: List[UUID]
):
    """
    Calculate and compare V^R scores for multiple companies.
    
    Returns comparison table showing V^R scores and penalty components.
    
    **Request Body:**
    ```json
    {
        "company_ids": [
            "c1a3b2f4-1111-4a8c-9c01-000000000001",
            "31715ac6-8556-4f84-89f5-1de9b847ff19",
            "c52e8f9d-09a2-4bbc-8c75-a5d3b6834fcf"
        ]
    }
    ```
    
    **Response:**
    ```json
    {
        "count": 3,
        "companies": {
            "CAT": {
                "company_id": "...",
                "company_name": "Caterpillar Inc.",
                "vr_score": 29.1,
                "base_score": 35.79,
                "cv": 0.749,
                "cv_penalty": 0.813,
                "talent_concentration": 0.15,
                "sector": "manufacturing"
            },
            "UNH": { ... },
            "WMT": { ... }
        }
    }
    ```
    
    Useful for:
    - Portfolio ranking
    - Identifying best/worst performers
    - Understanding penalty patterns across companies
    """
    try:
        comparison = {}
        
        for company_id in company_ids:
            try:
                result = scoring_service.calculate_vr(company_id)
                ticker = result["ticker"]
                
                comparison[ticker] = {
                    "company_id": str(company_id),
                    "company_name": result["company_name"],
                    "vr_score": result["vr_score"],
                    "base_score": result["vr_components"]["base_score"],
                    "cv": result["vr_components"]["cv"],
                    "cv_penalty": result["vr_components"]["cv_penalty"],
                    "talent_concentration": result["vr_components"]["talent_concentration"],
                    "talent_risk_adj": result["vr_components"]["talent_risk_adj"],
                    "sector": result["sector"]
                }
            except Exception as e:
                logger.error(
                    "vr_comparison_item_failed",
                    company_id=str(company_id),
                    error=str(e)
                )
                # Skip failed companies (don't fail entire comparison)
                continue
        
        if not comparison:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not calculate V^R for any of the provided companies. Check error logs."
            )
        
        return {
            "count": len(comparison),
            "companies": comparison
        }
    
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error("vr_comparison_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"V^R comparison failed: {str(e)}"
        )

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
    "/companies/{company_id}/org-air",
    summary="Calculate full Org-AI-R score (VR + HR + alignment + board governance)",
    response_model=Dict[str, Any],
)
async def calculate_org_air_score(company_id: UUID):
    """
    Calculate Org-AI-R score for a company via ScoringIntegrationService.

    Runs the full pipeline: CS1/CS2 evidence → VR → HR → alignment → Org-AI-R.
    """
    try:
        ticker = _get_ticker(company_id)
        result = integration_service.score_company(ticker)
        return result
    except ValueError as e:
        logger.error("org_air_data_error", company_id=str(company_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            "org_air_calculation_error",
            company_id=str(company_id),
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Org-AI-R calculation failed: {type(e).__name__}: {str(e)}",
        )


@router.post(
    "/companies/{company_id}/memo",
    summary="Generate PE-style investment memo",
    response_model=Dict[str, Any],
)
async def generate_investment_memo(company_id: UUID):
    """
    Generate an AI-readiness investment memo for a company.

    Pipeline:
    1. Run full scoring (Path A + Path B combined)
    2. Calculate V^R
    3. Feed scores + evidence into Claude to produce a PE-style memo

    **Response:**
    ```json
    {
        "markdown": "# Investment Memo: ...",
        "summary": {
            "recommendation": "BUY",
            "vr_score": 42.5,
            "top_strength": "talent",
            "top_weakness": "ai_governance",
            "discrepancy_flags": ["culture"]
        }
    }
    ```
    """
    try:
        # Step 1: Get dimension scores (combined Path A + B) with audit trail
        dimension_result = scoring_service.score_company(
            company_id=company_id, include_audit_trail=True
        )

        # Step 2: Extract Path A and Path B scores separately
        path_a_scores: Dict[str, float] = {}
        path_b_scores: Dict[str, Any] = {}
        evidence_metadata: Dict[str, str] = {}

        audit = dimension_result.get("audit_trail", {})
        rubric_details = audit.get("rubric_details", {})

        path_a_raw = audit.get("path_a_raw", {})
        for dim_name, dim_data in dimension_result["dimension_scores"].items():
            path_a_scores[dim_name] = path_a_raw.get(dim_name, dim_data["score"])
            if dim_name in rubric_details:
                path_b_scores[dim_name] = rubric_details[dim_name]

        # Step 3: Run full Org-AI-R pipeline via integration service
        ticker = dimension_result["ticker"]
        try:
            full_result = integration_service.score_company(ticker)
        except Exception as e:
            logger.warning(
                "integration_service_failed",
                ticker=ticker,
                error=str(e),
            )
            full_result = None

        # Step 4: Build vr_result dict that memo generator expects
        # (keys: vr_score, vr_components, dimension_scores, ticker, sector)
        if full_result:
            vr_result = {
                "vr_score": full_result["vr_score"],
                "ticker": full_result["ticker"],
                "sector": full_result["sector"],
                "dimension_scores": full_result["dimension_scores"],
                "vr_components": {
                    "base_score": full_result.get("vr_weighted_mean", 0.0),
                    "cv": full_result.get("vr_cv", 0.0),
                    "cv_penalty_amount": full_result.get("vr_cv_penalty_amount", 0.0),
                    "talent_concentration": full_result.get("talent_concentration", 0.0),
                    "tc_penalty_amount": full_result.get("vr_tc_penalty_amount", 0.0),
                },
            }
            # Use integration service's Path A/B for consistency with Combined
            if "path_a_scores" in full_result:
                path_a_scores = full_result["path_a_scores"]
            if "path_b_scores" in full_result:
                path_b_scores = full_result["path_b_scores"]
        else:
            # Fallback: compute VR via scoring_service if integration failed
            vr_result = scoring_service.calculate_vr(company_id=company_id)

        # Step 5: Generate memo
        markdown, summary = memo_generator.generate_memo(
            ticker=ticker,
            company_name=dimension_result["company_name"],
            path_a_scores=path_a_scores,
            path_b_scores=path_b_scores,
            vr_result=vr_result,
            evidence_metadata=evidence_metadata or None,
            full_scores=full_result,
        )

        # Step 6: Persist memo to S3
        s3_uri = upload_memo_to_s3(
            ticker=ticker,
            company_id=str(company_id),
            markdown=markdown,
            json_summary=summary,
        )

        return {"markdown": markdown, "summary": summary, "s3_uri": s3_uri}

    except ValueError as e:
        logger.error("memo_data_error", company_id=str(company_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            "memo_generation_error",
            company_id=str(company_id),
            error=str(e),
            error_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Memo generation failed: {type(e).__name__}: {str(e)}",
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
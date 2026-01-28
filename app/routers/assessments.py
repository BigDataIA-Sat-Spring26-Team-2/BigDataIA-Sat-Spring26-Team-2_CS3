from fastapi import APIRouter, HTTPException, status, Query
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timezone

from app.models.assessment import AssessmentCreate, AssessmentResponse
from app.models.enums import AssessmentStatus, AssessmentType

router = APIRouter(tags=["Assessments"])


# -------------------------
# POST /api/v1/assessments
# -------------------------
@router.post(
    "/assessments",
    response_model=AssessmentResponse,
    status_code=status.HTTP_201_CREATED
)
def create_assessment(payload: AssessmentCreate):
   
    now = datetime.now(timezone.utc)

    return AssessmentResponse(
        id=uuid4(),
        company_id=payload.company_id,
        assessment_type=payload.assessment_type,
        assessment_date=payload.assessment_date,
        primary_assessor=payload.primary_assessor,
        secondary_assessor=payload.secondary_assessor,
        status=AssessmentStatus.DRAFT,
        v_r_score=None,
        confidence_lower=None,
        confidence_upper=None,
        created_at=now,
    )


# ----------------------------------------
# GET /api/v1/assessments (filterable list)
# ----------------------------------------
@router.get(
    "/assessments",
    response_model=Dict[str, Any]  
)
def list_assessments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    company_id: Optional[UUID] = None,
    status_filter: Optional[AssessmentStatus] = Query(None, alias="status"),
    assessment_type: Optional[AssessmentType] = None,
):
 
    return {
        "items": [],
        "total": 0,
        "page": page,
        "page_size": page_size,
        "total_pages": 0,
        "filters": {
            "company_id": str(company_id) if company_id else None,
            "status": status_filter.value if status_filter else None,
            "assessment_type": assessment_type.value if assessment_type else None,
        }
    }


# -------------------------------------------------
# GET /api/v1/assessments/{id} (assessment + scores)
# -------------------------------------------------
@router.get(
    "/assessments/{assessment_id}",
    response_model=Dict[str, Any]
)
def get_assessment_with_scores(assessment_id: UUID):
   
    now = datetime.now(timezone.utc)

    fake_assessment = AssessmentResponse(
        id=assessment_id,
        company_id=uuid4(),
        assessment_type=AssessmentType.SCREENING,
        assessment_date=now,
        primary_assessor="Siddharth",
        secondary_assessor=None,
        status=AssessmentStatus.DRAFT,
        v_r_score=None,
        confidence_lower=None,
        confidence_upper=None,
        created_at=now,
    )

    return {
        "assessment": fake_assessment.model_dump(),
        "scores": []  
    }


# -------------------------------------------
# PATCH /api/v1/assessments/{id}/status
# -------------------------------------------
@router.patch(
    "/assessments/{assessment_id}/status",
    response_model=AssessmentResponse
)
def update_assessment_status(
    assessment_id: UUID,
    status_value: AssessmentStatus = Query(..., alias="status")
):
    """
    Stub: updates status and returns fake updated assessment.
    Later: update status in Snowflake and return real record.
    """
    now = datetime.now(timezone.utc)


    return AssessmentResponse(
        id=assessment_id,
        company_id=uuid4(),
        assessment_type=AssessmentType.SCREENING,
        assessment_date=now,
        primary_assessor="Siddharth",
        secondary_assessor=None,
        status=status_value,
        v_r_score=None,
        confidence_lower=None,
        confidence_upper=None,
        created_at=now,
    )

from fastapi import APIRouter, status, Query
from typing import Optional, Dict, Any
from uuid import UUID

from app.models.assessment import AssessmentCreate, AssessmentResponse
from app.models.enums import AssessmentStatus, AssessmentType
from app.models.pagination import PaginatedResponse
from app.services import assessments_service

router = APIRouter(tags=["Assessments"])


@router.post(
    "/assessments",
    response_model=AssessmentResponse,
    status_code=status.HTTP_201_CREATED
)
def create_assessment(payload: AssessmentCreate):
    print("🔥 ROUTER HIT: add_dimension_scores", flush=True)
    return assessments_service.create_assessment(payload)


@router.get(
    "/assessments",
    response_model=PaginatedResponse[AssessmentResponse]
)
def list_assessments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    company_id: Optional[UUID] = None,
    status_filter: Optional[AssessmentStatus] = Query(None, alias="status"),
    assessment_type: Optional[AssessmentType] = None,
):
    return assessments_service.list_assessments(
        company_id=company_id,
        page=page,
        page_size=page_size,
        status=status_filter,
        assessment_type=assessment_type,
    )


@router.get("/assessments/{assessment_id}")
def get_assessment_with_scores(assessment_id: UUID):
    return assessments_service.get_assessment_with_scores(assessment_id)


@router.patch(
    "/assessments/{assessment_id}/status",
    response_model=AssessmentResponse
)
def update_assessment_status(
    assessment_id: UUID,
    status_value: AssessmentStatus = Query(..., alias="status"),
):
    return assessments_service.update_assessment_status(
        assessment_id,
        status_value,
    )

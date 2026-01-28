from fastapi import APIRouter, HTTPException, status, Query
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timezone
from app.models.assessment import AssessmentCreate, AssessmentResponse
from app.models.enums import AssessmentStatus, AssessmentType
from app.services import assessments_service

router = APIRouter(tags=["Assessments"])


@router.post(
    "/assessments",
    response_model=AssessmentResponse,
)
def create_assessment(payload: AssessmentCreate):
    return assessments_service.create_assessment(payload)


@router.get("/assessments")
def list_assessments(
    company_id: UUID = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: AssessmentStatus | None = Query(None, alias="status"),
    assessment_type: AssessmentType | None = None,
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

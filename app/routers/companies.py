from fastapi import APIRouter, status, Query
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timezone

from app.models.company import CompanyCreate, CompanyResponse

router = APIRouter(tags=["Companies"])


@router.post(
    "/companies",
    response_model=CompanyResponse,
    status_code=status.HTTP_201_CREATED
)
def create_company(payload: CompanyCreate):
    now = datetime.now(timezone.utc)

    return CompanyResponse(
        id=uuid4(),
        name=payload.name,
        ticker=payload.ticker,
        industry_id=payload.industry_id,
        position_factor=payload.position_factor,
        created_at=now,
        updated_at=now,
    )


@router.get(
    "/companies",
    response_model=Dict[str, Any]
)
def list_companies(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    industry_id: Optional[UUID] = None,
):
    return {
        "items": [],
        "total": 0,
        "page": page,
        "page_size": page_size,
        "total_pages": 0,
        "filters": {
            "industry_id": str(industry_id) if industry_id else None
        }
    }

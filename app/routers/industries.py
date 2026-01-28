from fastapi import APIRouter, Query, status
from typing import Optional, List
from uuid import UUID

from app.models.industry import IndustryCreate, IndustryResponse
from app.models.enums import Sector
from app.models.pagination import PaginatedResponse
from app.services import industry_service

router = APIRouter(tags=["Industries"])


@router.post(
    "/industries",
    response_model=IndustryResponse,
    status_code=status.HTTP_201_CREATED
)
def create_industry(payload: IndustryCreate):
    return industry_service.create_industry(payload)


@router.get(
    "/industries",
    response_model=PaginatedResponse[IndustryResponse]
)
def list_industries(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sector: Optional[Sector] = None,
    name_contains: Optional[str] = Query(None, alias="name"),
):
    return industry_service.list_industries(
        page=page,
        page_size=page_size,
        sector=sector,
        name_contains=name_contains,
    )


@router.get(
    "/industries/{industry_id}",
    response_model=IndustryResponse
)
def get_industry(industry_id: UUID):
    return industry_service.get_industry_by_id(industry_id)


@router.get("/sectors", response_model=List[str])
def list_sectors():
    return [s.value for s in Sector]

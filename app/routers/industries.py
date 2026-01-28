# app/routers/industries.py
from fastapi import APIRouter, Query
from typing import Optional, List
from uuid import UUID, uuid4
from app.models.industry import IndustryCreate, IndustryResponse
from app.models.enums import Sector
from app.services import industry_service

router = APIRouter(tags=["Industries"])

# POST API
@router.post(
    "/industries",
    response_model=IndustryResponse,
)
def create_industry(payload: IndustryCreate):
    return industry_service.create_industry(payload)

# GET API
@router.get("/industries")
def list_industries(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sector: Sector = Query(...),
    name_contains: Optional[str] = Query(None, alias="name"),
):
    return industry_service.list_industries(
        page=page,
        page_size=page_size,
        sector=sector,
        name_contains=name_contains,
    )


# GET by ID
@router.get(
    "/industries/{industry_id}",
    response_model=IndustryResponse
)
def get_industry(industry_id: UUID):
    return industry_service.get_industry_by_id(industry_id)


# GET Sectors
@router.get("/sectors", response_model=List[str])
def list_sectors():
    return [s.value for s in Sector]
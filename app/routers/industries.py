# app/routers/industries.py
from fastapi import APIRouter, HTTPException, status, Query
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4
from datetime import datetime, timezone

from app.models.industry import IndustryCreate, IndustryResponse
from app.models.enums import Sector

router = APIRouter(tags=["Industries"])

# -------------------------
# POST /api/v1/industries
# -------------------------
@router.post(
    "/industries",
    response_model=IndustryResponse,
    status_code=status.HTTP_201_CREATED
)
def create_industry(payload: IndustryCreate):
    now = datetime.now(timezone.utc)

    return IndustryResponse(
        id=uuid4(),
        name=payload.name,
        sector=payload.sector,
        h_r_base=payload.h_r_base,
        created_at=now,
    )


# ----------------------------------------
# GET /api/v1/industries (filterable list)
# ----------------------------------------
@router.get(
    "/industries",
    response_model=Dict[str, Any]
)
def list_industries(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sector: Optional[Sector] = None,
    name_contains: Optional[str] = Query(None, alias="name")
):

    return {
        "items": [],
        "total": 0,
        "page": page,
        "page_size": page_size,
        "total_pages": 0,
        "filters": {
            "sector": sector.value if sector else None,
            "name": name_contains,
        }
    }


# -------------------------------------------
# GET /api/v1/industries/{industry_id}
# -------------------------------------------
@router.get(
    "/industries/{industry_id}",
    response_model=IndustryResponse
)
def get_industry(industry_id: UUID):
   
    now = datetime.now(timezone.utc)

    return IndustryResponse(
        id=industry_id,
        name="Manufacturing",
        sector=Sector.INDUSTRIALS,
        h_r_base=72.0,
        created_at=now,
    )


# -------------------------------------------
# GET /api/v1/sectors  (enum helper)
# -------------------------------------------
@router.get(
    "/sectors",
    response_model=List[str]
)
def list_sectors():
   
    return [s.value for s in Sector]

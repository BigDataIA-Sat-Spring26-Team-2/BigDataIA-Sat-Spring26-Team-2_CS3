from fastapi import APIRouter, status, Query
from typing import Optional
from uuid import UUID

from app.services import company_service
from app.models.company import CompanyCreate, CompanyResponse
from app.models.pagination import PaginatedResponse 

router = APIRouter(tags=["Companies"])


@router.post(
    "/companies",
    response_model=CompanyResponse,
    status_code=status.HTTP_201_CREATED  
)
def create_company(payload: CompanyCreate):
    return company_service.create_company(payload)


@router.get(
    "/companies",
    response_model=PaginatedResponse[CompanyResponse] 
)
def list_companies(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    industry_id: Optional[UUID] = None,
):
    return company_service.list_companies(
        page=page,
        page_size=page_size,
        industry_id=industry_id,
    )


@router.get(
    "/companies/{company_id}",
    response_model=CompanyResponse
)
def get_company(company_id: UUID):
    return company_service.get_company_by_id(company_id)


@router.put(
    "/companies/{company_id}",
    response_model=CompanyResponse
)
def update_company(company_id: UUID, payload: CompanyCreate):
    return company_service.update_company(company_id, payload)


@router.delete(
    "/companies/{company_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_company(company_id: UUID):
    company_service.delete_company(company_id)
    return None

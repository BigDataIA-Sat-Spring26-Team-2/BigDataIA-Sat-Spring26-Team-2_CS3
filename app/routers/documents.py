from fastapi import APIRouter, Query, HTTPException, status
from uuid import UUID
from typing import List, Optional

from app.services import sec_edgar_service

router = APIRouter(tags=["Documents"])


@router.post(
    "/companies/{company_id}/sec-edgar/download",
    status_code=status.HTTP_200_OK,
)
def download_sec_filings(
    company_id: UUID,
    ticker: Optional[str] = Query(None, min_length=1, max_length=10),
    cik: Optional[str] = Query(None, min_length=10, max_length=10),
    filing_types: List[str] = Query(default=["10-K", "10-Q", "8-K"]),
    after: str = Query(default="2020-01-01"),
    limit: int = Query(default=10, ge=1, le=50),
):
    # require one of ticker or cik
    if not ticker and not cik:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either ticker or cik",
        )

    if ticker:
        ticker = ticker.upper()

    return sec_edgar_service.run_sec_download_for_company(
        company_id=company_id,
        ticker=ticker,
        cik=cik,
        filing_types=filing_types,
        limit=limit,
        after=after,
    )

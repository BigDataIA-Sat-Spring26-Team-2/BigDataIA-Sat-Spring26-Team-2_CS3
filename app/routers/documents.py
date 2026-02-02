from pathlib import Path
from fastapi import APIRouter, Query, HTTPException, status
from fastapi.responses import FileResponse
from uuid import UUID
from typing import List, Optional

from app.services import sec_edgar_service

router = APIRouter(prefix="/documents", tags=["Documents"])

BASE_SEC_DIR = Path("data/raw/sec").resolve()


@router.post(
    "/sec-edgar/download",
    status_code=status.HTTP_200_OK,
)
def download_sec_filings(
    company_id: UUID = Query(...),
    ticker: Optional[str] = Query(None, min_length=1, max_length=10),
    cik: Optional[str] = Query(None, min_length=10, max_length=10),
    filing_types: List[str] = Query(default=["10-K", "10-Q", "8-K"]),
    after: str = Query(default="2020-01-01"),
    limit: int = Query(default=10, ge=1, le=50),
):
    if not ticker and not cik:
        raise HTTPException(status_code=400, detail="Provide either ticker or cik")
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


@router.get("/file", response_class=FileResponse, status_code=status.HTTP_200_OK)
def download_local_file(path: str = Query(...)):
    p = Path(path).resolve()

    if BASE_SEC_DIR not in p.parents and p != BASE_SEC_DIR:
        raise HTTPException(status_code=403, detail="Forbidden path")

    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(path=str(p), filename=p.name, media_type="text/plain")

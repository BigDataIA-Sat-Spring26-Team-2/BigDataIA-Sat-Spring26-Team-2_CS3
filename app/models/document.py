from __future__ import annotations

from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional, Dict


class DocumentCreate(BaseModel):
    company_id: UUID
    ticker: str = Field(..., min_length=1, max_length=10)
    filing_type: str = Field(..., min_length=2, max_length=20)
    accession_number: str = Field(..., min_length=5, max_length=50)
    source_path: str = Field(..., min_length=1, max_length=2000)
    content_hash: str = Field(..., min_length=64, max_length=64)  # sha256
    filing_date: datetime
    word_count: int = Field(..., ge=0)
    sections: Dict[str, str] = Field(default_factory=dict)


class DocumentResponse(DocumentCreate):
    id: UUID
    created_at: datetime

from __future__ import annotations

from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional


class EvidenceChunkCreate(BaseModel):
    document_id: UUID
    chunk_index: int = Field(..., ge=0)
    text: str = Field(..., min_length=1)
    content_hash: str = Field(..., min_length=64, max_length=64)
    word_count: int = Field(..., ge=0)


class EvidenceChunkResponse(EvidenceChunkCreate):
    id: UUID
    created_at: datetime

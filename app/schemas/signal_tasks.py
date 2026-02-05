from pydantic import BaseModel
from uuid import UUID

class QueuedTaskResponse(BaseModel):
    status: str  # "queued"
    message: str
    company_id: UUID
    ticker: str
    assignee: str

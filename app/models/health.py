from pydantic import BaseModel
from datetime import datetime
from typing import Dict


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    version: str
    dependencies: Dict[str, str]

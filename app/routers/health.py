from fastapi import APIRouter, HTTPException, status
from typing import List
from uuid import UUID, uuid4
from datetime import datetime, timezone
from pydantic import BaseModel
from typing import Dict
 
from app.models.dimension import DimensionScoreCreate, DimensionScoreResponse
from app.services.redis_cache import check_redis
 
router = APIRouter(tags=["Health"])
class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    version: str
    dependencies: Dict[str, str]
 
 
@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
)
async def health_check():
    dependencies = {
        "redis": await check_redis(),
    }
 
    all_healthy = all(v == "healthy" for v in dependencies.values())
 
    return HealthResponse(
        status="healthy" if all_healthy else "degraded",
        timestamp=datetime.now(timezone.utc),
        version="1.0.0",
        dependencies=dependencies,
    )
 
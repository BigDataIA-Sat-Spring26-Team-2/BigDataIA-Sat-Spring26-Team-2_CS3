from fastapi import APIRouter, Response, status
from datetime import datetime, timezone

from app.models.health import HealthResponse
from app.services.snowflake import check_snowflake
from app.services.redis_cache import check_redis
from app.services.s3_storage import check_s3

router = APIRouter()

@router.get("/health", response_model=HealthResponse)
async def health_check(response: Response):
    dependencies = {
        "snowflake": await check_snowflake(),
        "redis": await check_redis(),
        "s3": await check_s3(),
    }

    all_healthy = all(v == "healthy" for v in dependencies.values())

    response.status_code = (
        status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    )

    return HealthResponse(
        status="healthy" if all_healthy else "degraded",
        timestamp=datetime.now(timezone.utc),
        version="1.0.0",
        dependencies=dependencies
    )

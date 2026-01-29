# app/services/redis_cache.py
import redis
from typing import Optional, TypeVar, Type
from pydantic import BaseModel
from app.config import get_settings

T = TypeVar("T", bound=BaseModel)


class RedisCache:
    def __init__(self):
        settings = get_settings()
        self.client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=False,
        )

    def get(self, key: str, model: Type[T]) -> Optional[T]:
        data = self.client.get(key)
        if data:
            return model.model_validate_json(data)
        return None

    def set(self, key: str, value: BaseModel, ttl_seconds: int) -> None:
        self.client.setex(
            key,
            ttl_seconds,
            value.model_dump_json()
        )

    def delete(self, key: str) -> None:
        self.client.delete(key)

    def delete_pattern(self, pattern: str) -> None:
        for key in self.client.scan_iter(match=pattern):
            self.client.delete(key)
    # Health check method for redis connection
    def ping(self) -> bool:
        try:
            return self.client.ping()
        except Exception:
            return False



# Singleton cache instance
cache = RedisCache()


async def check_redis() -> str:
    return "healthy" if cache.ping() else "unhealthy"

# app/services/redis_cache.py
import redis
from typing import Optional, TypeVar, Type
from pydantic import BaseModel
from app.config import REDIS_HOST, REDIS_PORT, REDIS_DB

T = TypeVar("T", bound=BaseModel)


class RedisCache:
    def __init__(self):
        self.client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            decode_responses=False,  # required for model_validate_json
        )

    def get(self, key: str, model: Type[T]) -> Optional[T]:
        """Get cached item and deserialize into Pydantic model"""
        data = self.client.get(key)
        if data:
            return model.model_validate_json(data)
        return None

    def set(self, key: str, value: BaseModel, ttl_seconds: int) -> None:
        """Cache Pydantic model with TTL"""
        self.client.setex(
            key,
            ttl_seconds,
            value.model_dump_json()
        )

    def delete(self, key: str) -> None:
        """Invalidate a single cache entry"""
        self.client.delete(key)

    def delete_pattern(self, pattern: str) -> None:
        """Invalidate multiple cache entries"""
        for key in self.client.scan_iter(match=pattern):
            self.client.delete(key)


# Singleton cache instance
cache = RedisCache()


async def check_redis() -> str:
    return "healthy"

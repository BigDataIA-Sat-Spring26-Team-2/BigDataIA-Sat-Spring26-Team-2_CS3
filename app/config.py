from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import os


class Settings(BaseSettings):
    """
    Centralized configuration for the app.
    Values come from environment variables (and optionally a .env file).
    """

    # ---- Snowflake ----
    SNOWFLAKE_ACCOUNT: str = Field(..., description="Snowflake account identifier")
    SNOWFLAKE_USER: str = Field(..., description="Snowflake username")
    SNOWFLAKE_PASSWORD: str = Field(..., description="Snowflake password")
    SNOWFLAKE_DATABASE: str = Field(..., description="Snowflake database name")
    SNOWFLAKE_SCHEMA: str = Field(..., description="Snowflake schema name")
    SNOWFLAKE_WAREHOUSE: str = Field(..., description="Snowflake warehouse name")

    # Optional in case your setup requires it
    SNOWFLAKE_ROLE: str | None = Field(default=None, description="Snowflake role (optional)")

    # ---- Redis ----
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # ---- AWS / S3 ----
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    S3_BUCKET: str | None = None

    # ---- App metadata ----
    APP_ENV: str = Field("local", description="Environment name: local/dev/prod")
    APP_VERSION: str = Field("1.0.0", description="App version string")

    # This tells Pydantic Settings to load from .env if it exists
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # ignore unknown env vars (safe)
    )


@lru_cache
def get_settings() -> Settings:
    """
    Cached settings instance so we don't reload env vars repeatedly.
    """
    return Settings()

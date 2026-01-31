import os
import uuid
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from dotenv import load_dotenv
load_dotenv()

def make_uuid() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def ids():
    return {
        "industry_id": make_uuid(),
        "company_id": make_uuid(),
        "assessment_id": make_uuid(),
        "score_id": make_uuid(),
    }


@pytest.fixture
def build_test_client():
    """
    Builds a FastAPI app including your real routers.
    Service calls must be monkeypatched in each test module
    to avoid hitting Snowflake.
    """
    def _build():
        from app.routers import assessments, companies, dimension_scores, industries, health

        app = FastAPI()
        app.include_router(health.router, prefix="/api/v1")
        app.include_router(companies.router, prefix="/api/v1")
        app.include_router(assessments.router, prefix="/api/v1")
        app.include_router(dimension_scores.router, prefix="/api/v1")
        app.include_router(industries.router, prefix="/api/v1")
        return TestClient(app)

    return _build


def snowflake_env_present() -> bool:
    required = [
        "SNOWFLAKE_ACCOUNT",
        "SNOWFLAKE_USER",
        "SNOWFLAKE_PASSWORD",
        "SNOWFLAKE_DATABASE",
        "SNOWFLAKE_SCHEMA",
        "SNOWFLAKE_WAREHOUSE",
    ]
    return all(os.getenv(k) for k in required)


pytestmark_integration = pytest.mark.integration

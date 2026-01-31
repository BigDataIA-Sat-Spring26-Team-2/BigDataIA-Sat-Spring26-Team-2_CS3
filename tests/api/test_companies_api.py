from uuid import uuid4
from datetime import datetime, timezone
from fastapi import HTTPException

from app.models.company import CompanyResponse


def test_create_company_201(monkeypatch, build_test_client):
    from app.services import company_service

    def fake_create_company(payload):
        now = datetime.now(timezone.utc)
        return CompanyResponse(
            id=uuid4(),
            name=payload.name,
            ticker=payload.ticker,
            industry_id=payload.industry_id,
            position_factor=payload.position_factor,
            created_at=now,
            updated_at=now,
        )

    monkeypatch.setattr(company_service, "create_company", fake_create_company)
    client = build_test_client()

    resp = client.post("/api/v1/companies", json={
        "name": "X",
        "ticker": "abc",
        "industry_id": str(uuid4()),
        "position_factor": 0.0
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["ticker"] == "ABC"


def test_companies_pagination_query_validation(build_test_client):
    client = build_test_client()
    resp = client.get("/api/v1/companies?page=0&page_size=20")
    assert resp.status_code == 422


def test_create_company_fk_404(monkeypatch, build_test_client):
    from app.services import company_service

    def fake_create_company(payload):
        raise HTTPException(status_code=404, detail="Industry not found")

    monkeypatch.setattr(company_service, "create_company", fake_create_company)
    client = build_test_client()

    resp = client.post("/api/v1/companies", json={
        "name": "Bad",
        "ticker": "BAD",
        "industry_id": str(uuid4()),
        "position_factor": 0.0
    })
    assert resp.status_code == 404

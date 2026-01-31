from uuid import uuid4
from datetime import datetime, timezone
from fastapi import HTTPException

from app.models.assessment import AssessmentResponse
from app.models.enums import AssessmentType, AssessmentStatus


def test_create_assessment_201(monkeypatch, build_test_client):
    from app.services import assessments_service

    def fake_create(payload):
        now = datetime.now(timezone.utc)
        return AssessmentResponse(
            id=uuid4(),
            company_id=payload.company_id,
            assessment_type=payload.assessment_type,
            assessment_date=payload.assessment_date,
            primary_assessor=payload.primary_assessor,
            secondary_assessor=payload.secondary_assessor,
            status=AssessmentStatus.DRAFT,
            v_r_score=None,
            confidence_lower=None,
            confidence_upper=None,
            created_at=now,
        )

    monkeypatch.setattr(assessments_service, "create_assessment", fake_create)
    client = build_test_client()

    resp = client.post(
        "/api/v1/assessments",
        json={
            "company_id": str(uuid4()),
            "assessment_type": "screening",
            "primary_assessor": "QA",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "draft"


def test_create_assessment_invalid_enum_422(build_test_client):
    client = build_test_client()
    resp = client.post(
        "/api/v1/assessments",
        json={
            "company_id": str(uuid4()),
            "assessment_type": "NOT_A_REAL_TYPE",
        },
    )
    assert resp.status_code == 422


def test_list_assessments_page_validation_422(build_test_client):
    client = build_test_client()
    resp = client.get("/api/v1/assessments?page=0&page_size=20")
    assert resp.status_code == 422


def test_list_assessments_page_size_validation_422(build_test_client):
    client = build_test_client()
    resp = client.get("/api/v1/assessments?page=1&page_size=101")
    assert resp.status_code == 422


def test_list_assessments_200_shape(monkeypatch, build_test_client):
    from app.services import assessments_service

    def fake_list(company_id, page, page_size, status, assessment_type):
        return {
            "items": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
            "total_pages": 0,
        }

    monkeypatch.setattr(assessments_service, "list_assessments", fake_list)
    client = build_test_client()

    resp = client.get(
        "/api/v1/assessments",
        params={
            "company_id": str(uuid4()),
            "page": 1,
            "page_size": 20,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size", "total_pages"}


def test_get_assessment_with_scores_200(monkeypatch, build_test_client):
    from app.services import assessments_service

    def fake_get(assessment_id):
        now = datetime.now(timezone.utc)
        return {
            "assessment": AssessmentResponse(
                id=assessment_id,
                company_id=uuid4(),
                assessment_type=AssessmentType.SCREENING,
                assessment_date=now,
                primary_assessor="QA",
                secondary_assessor=None,
                status=AssessmentStatus.DRAFT,
                v_r_score=None,
                confidence_lower=None,
                confidence_upper=None,
                created_at=now,
            ),
            "scores": [],
        }

    monkeypatch.setattr(assessments_service, "get_assessment_with_scores", fake_get)
    client = build_test_client()

    a = uuid4()
    resp = client.get(f"/api/v1/assessments/{a}")
    assert resp.status_code == 200
    body = resp.json()
    assert "assessment" in body and "scores" in body
    assert body["assessment"]["id"] == str(a)


def test_update_status_invalid_enum_422(build_test_client):
    client = build_test_client()
    resp = client.patch(f"/api/v1/assessments/{uuid4()}/status?status=NOT_A_REAL_STATUS")
    assert resp.status_code == 422


def test_update_status_invalid_transition_400(monkeypatch, build_test_client):
    from app.services import assessments_service

    def fake_update(assessment_id, status_value):
        raise HTTPException(status_code=400, detail="Invalid status transition")

    monkeypatch.setattr(assessments_service, "update_assessment_status", fake_update)
    client = build_test_client()

    resp = client.patch(f"/api/v1/assessments/{uuid4()}/status?status=approved")
    assert resp.status_code == 400


def test_update_status_valid_200(monkeypatch, build_test_client):
    from app.services import assessments_service

    def fake_update(assessment_id, status_value):
        now = datetime.now(timezone.utc)
        return AssessmentResponse(
            id=assessment_id,
            company_id=uuid4(),
            assessment_type=AssessmentType.SCREENING,
            assessment_date=now,
            primary_assessor="QA",
            secondary_assessor=None,
            status=status_value,
            v_r_score=None,
            confidence_lower=None,
            confidence_upper=None,
            created_at=now,
        )

    monkeypatch.setattr(assessments_service, "update_assessment_status", fake_update)
    client = build_test_client()

    resp = client.patch(f"/api/v1/assessments/{uuid4()}/status?status=in_progress")
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"

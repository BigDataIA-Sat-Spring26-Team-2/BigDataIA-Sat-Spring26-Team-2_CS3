from uuid import uuid4
from datetime import datetime, timezone
from fastapi import HTTPException

from app.models.dimension import DimensionScoreResponse
from app.models.enums import Dimension


def test_dimension_scores_body_path_mismatch(monkeypatch, build_test_client):
    from app.services import dimension_scores_service

    def fake_add(assessment_id, scores):
        raise HTTPException(status_code=400, detail="assessment_id in body must match path parameter")

    monkeypatch.setattr(dimension_scores_service, "add_dimension_scores", fake_add)
    client = build_test_client()

    a = uuid4()
    b = uuid4()
    resp = client.post(f"/api/v1/assessments/{a}/scores", json=[{
        "assessment_id": str(b),
        "dimension": "data_infrastructure",
        "score": 80,
        "confidence": 0.9,
        "evidence_count": 2
    }])
    assert resp.status_code == 400


def test_dimension_scores_add_201(monkeypatch, build_test_client):
    from app.services import dimension_scores_service

    def fake_add(assessment_id, scores):
        now = datetime.now(timezone.utc)
        return [
            DimensionScoreResponse(
                id=uuid4(),
                assessment_id=assessment_id,
                dimension=Dimension.DATA_INFRASTRUCTURE,
                score=80,
                weight=0.25,
                confidence=0.9,
                evidence_count=2,
                created_at=now,
            )
        ]

    monkeypatch.setattr(dimension_scores_service, "add_dimension_scores", fake_add)
    client = build_test_client()

    a = uuid4()
    resp = client.post(f"/api/v1/assessments/{a}/scores", json=[{
        "assessment_id": str(a),
        "dimension": "data_infrastructure",
        "score": 80,
        "confidence": 0.9,
        "evidence_count": 2
    }])
    assert resp.status_code == 201

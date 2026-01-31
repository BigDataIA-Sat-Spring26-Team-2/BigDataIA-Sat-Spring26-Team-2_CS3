import pytest
from uuid import uuid4, UUID
from datetime import datetime, timezone

from app.config import get_settings
from app.services.snowflake import get_connection
from app.services import assessments_service
from tests.conftest import snowflake_env_present


def _fq(name: str) -> str:
    s = get_settings()
    return f"{s.SNOWFLAKE_DATABASE}.{s.SNOWFLAKE_SCHEMA}.{name}"


@pytest.mark.integration
@pytest.mark.skipif(not snowflake_env_present(), reason="Snowflake env not set")
def test_assessment_create_get_list_and_status_transitions():
    industries = _fq("INDUSTRIES")
    companies = _fq("COMPANIES")
    assessments = _fq("ASSESSMENTS")

    industry_id = str(uuid4())
    company_id = str(uuid4())
    now = datetime.now(timezone.utc)

    conn = get_connection()
    cur = conn.cursor()

    try:
        # prereq industry
        cur.execute(
            f"INSERT INTO {industries} (id, name, sector, h_r_base, created_at) VALUES (%s, %s, %s, %s, %s)",
            (industry_id, "TestInd", "Healthcare", 50, now),
        )

        # prereq company
        cur.execute(
            f"""INSERT INTO {companies}
                (id, name, ticker, industry_id, position_factor, is_deleted, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, FALSE, %s, %s)
            """,
            (company_id, "TestCo", "TCO", industry_id, 0.0, now, now),
        )
        conn.commit()

        # create assessment via service (your real code)
        payload = {
            "company_id": UUID(company_id),
            "assessment_type": "screening",
            "primary_assessor": "QA",
            "secondary_assessor": None,
        }
        # build AssessmentCreate without importing your model directly as dict
        from app.models.assessment import AssessmentCreate
        from app.models.enums import AssessmentType
        create_payload = AssessmentCreate(
            company_id=UUID(company_id),
            assessment_type=AssessmentType.SCREENING,
            primary_assessor="QA",
            secondary_assessor=None,
        )

        created = assessments_service.create_assessment(create_payload)
        assert created.company_id == UUID(company_id)
        assert created.assessment_type.value == "screening"
        assert created.status.value == "draft"

        assessment_id = created.id

        # get assessment with scores
        got = assessments_service.get_assessment_with_scores(assessment_id)
        assert "assessment" in got and "scores" in got
        assert got["assessment"].id == assessment_id

        # list assessments pagination
        listed = assessments_service.list_assessments(
            company_id=UUID(company_id),
            page=1,
            page_size=1,
            status_filter=None,
            assessment_type=None,
        )
        assert listed["page"] == 1
        assert listed["page_size"] == 1
        assert listed["total"] >= 1
        assert len(listed["items"]) == 1

        # valid transition: draft -> in_progress
        from app.models.enums import AssessmentStatus
        updated = assessments_service.update_assessment_status(assessment_id, AssessmentStatus.IN_PROGRESS)
        assert updated.status.value == "in_progress"

        # invalid transition: in_progress -> approved (should fail unless your map allows it)
        # If your state machine requires: in_progress -> submitted first, this should be 400
        with pytest.raises(Exception) as ex:
            assessments_service.update_assessment_status(assessment_id, AssessmentStatus.APPROVED)
        # allow either HTTPException(400) or your app error wrapper
        assert "400" in str(ex.value) or "Invalid status transition" in str(ex.value)

        # cleanup assessment row
        cur.execute(f"DELETE FROM {assessments} WHERE id=%s", (str(assessment_id),))
        conn.commit()

    finally:
        # best-effort cleanup
        try:
            cur.execute(f"UPDATE {companies} SET is_deleted=TRUE WHERE id=%s", (company_id,))
            cur.execute(f"DELETE FROM {industries} WHERE id=%s", (industry_id,))
            conn.commit()
        except Exception:
            pass
        cur.close()
        conn.close()

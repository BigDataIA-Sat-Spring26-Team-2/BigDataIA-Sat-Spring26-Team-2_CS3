import pytest
from uuid import uuid4
from datetime import datetime, timezone

from app.config import get_settings
from app.services.snowflake import get_connection
from tests.conftest import snowflake_env_present


def _fq(name: str) -> str:
    s = get_settings()
    return f"{s.SNOWFLAKE_DATABASE}.{s.SNOWFLAKE_SCHEMA}.{name}"


@pytest.mark.integration
@pytest.mark.skipif(not snowflake_env_present(), reason="Snowflake env not set")
def test_dimension_scores_insert_and_list():
    industries = _fq("INDUSTRIES")
    companies = _fq("COMPANIES")
    assessments = _fq("ASSESSMENTS")
    scores = _fq("DIMENSION_SCORES")

    industry_id = str(uuid4())
    company_id = str(uuid4())
    assessment_id = str(uuid4())
    score_id = str(uuid4())
    now = datetime.now(timezone.utc)

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            f"INSERT INTO {industries} (id, name, sector, h_r_base, created_at) VALUES (%s, %s, %s, %s, %s)",
            (industry_id, "Ind", "HEALTHCARE", 50, now),
        )
        cur.execute(
            f"""INSERT INTO {companies}
                (id, name, ticker, industry_id, position_factor, is_deleted, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, FALSE, %s, %s)
            """,
            (company_id, "Co", "CO", industry_id, 0.0, now, now),
        )
        cur.execute(
            f"""INSERT INTO {assessments}
                (id, company_id, assessment_type, assessment_date, status,
                 primary_assessor, secondary_assessor, v_r_score, confidence_lower, confidence_upper, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NULL, NULL, NULL, %s)
            """,
            (assessment_id, company_id, "SCREENING", now.date(), "DRAFT", "Tester", None, now),
        )

        cur.execute(
            f"""INSERT INTO {scores}
                (id, assessment_id, dimension, score, weight, confidence, evidence_count, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (score_id, assessment_id, "DATA_INFRASTRUCTURE", 80, 0.25, 0.9, 2, now),
        )
        conn.commit()

        cur.execute(f"SELECT COUNT(*) FROM {scores} WHERE assessment_id=%s", (assessment_id,))
        total = cur.fetchone()[0]
        assert total >= 1

    finally:
        cur.execute(f"DELETE FROM {scores} WHERE assessment_id=%s", (assessment_id,))
        cur.execute(f"DELETE FROM {assessments} WHERE id=%s", (assessment_id,))
        cur.execute(f"UPDATE {companies} SET is_deleted=TRUE WHERE id=%s", (company_id,))
        cur.execute(f"DELETE FROM {industries} WHERE id=%s", (industry_id,))
        conn.commit()
        cur.close()
        conn.close()

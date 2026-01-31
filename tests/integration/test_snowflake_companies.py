import pytest
from uuid import uuid4, UUID
from datetime import datetime, timezone

from app.config import get_settings
from app.services.snowflake import get_connection
from tests.conftest import snowflake_env_present


def _fq(name: str) -> str:
    s = get_settings()
    return f"{s.SNOWFLAKE_DATABASE}.{s.SNOWFLAKE_SCHEMA}.{name}"


@pytest.mark.integration
@pytest.mark.skipif(not snowflake_env_present(), reason="Snowflake env not set")
def test_company_fk_industry_exists_and_persists():
    industries = _fq("INDUSTRIES")
    companies = _fq("COMPANIES")

    industry_id = str(uuid4())
    company_id = str(uuid4())
    now = datetime.now(timezone.utc)

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            f"INSERT INTO {industries} (id, name, sector, h_r_base, created_at) VALUES (%s, %s, %s, %s, %s)",
            (industry_id, "TestIndustry", "HEALTHCARE", 50, now),
        )

        cur.execute(
            f"""INSERT INTO {companies}
                (id, name, ticker, industry_id, position_factor, is_deleted, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, FALSE, %s, %s)
            """,
            (company_id, "TestCo", "TCO", industry_id, 0.0, now, now),
        )

        conn.commit()

        cur.execute(f"SELECT id, name, ticker, industry_id FROM {companies} WHERE id=%s", (company_id,))
        row = cur.fetchone()
        assert row is not None
        assert row[0] == company_id
        assert row[1] == "TestCo"
        assert row[2] == "TCO"
        assert row[3] == industry_id

    finally:
        cur.execute(f"UPDATE {companies} SET is_deleted=TRUE WHERE id=%s", (company_id,))
        cur.execute(f"DELETE FROM {industries} WHERE id=%s", (industry_id,))
        conn.commit()
        cur.close()
        conn.close()

from uuid import uuid4
from datetime import datetime, timezone
from typing import List
from app.models.leadership import ExecutiveProfile
from app.services.snowflake import get_connection
from app.config import get_settings

def _fq(name: str) -> str:
    s = get_settings()
    return f"{s.SNOWFLAKE_DATABASE}.{s.SNOWFLAKE_SCHEMA}.{name}"

EXTERNAL_SIGNALS_TABLE = _fq("EXTERNAL_SIGNALS")


def compute_leadership_score(executives: List[ExecutiveProfile]) -> float:
    if not executives:
        return 0.0

    weighted_sum = sum(
        exec.role_weight * exec.ai_score()
        for exec in executives
    )

    return round(weighted_sum / len(executives), 4)


def store_leadership_signal(
    company_id: str,
    signal_source: str,
    executives: List[ExecutiveProfile],
):
    leadership_score = compute_leadership_score(executives)

    conn = get_connection()
    cur = conn.cursor()

    try:
        for exec in executives:
            raw = exec.ai_score()
            normalized = raw  # already 0–1

            cur.execute(
                f"""
                INSERT INTO {EXTERNAL_SIGNALS_TABLE} (
                    id,
                    company_id,
                    signal_type,
                    signal_source,
                    signal_name,
                    raw_value,
                    normalized_value,
                    weight,
                    signal_score,
                    calculated_at
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    str(uuid4()),
                    company_id,
                    "leadership",
                    signal_source,
                    exec.title.lower().replace(" ", "_"),
                    raw,
                    normalized,
                    exec.role_weight,
                    leadership_score,
                    datetime.now(timezone.utc),
                ),
            )

        conn.commit()

    finally:
        cur.close()
        conn.close()

    return leadership_score

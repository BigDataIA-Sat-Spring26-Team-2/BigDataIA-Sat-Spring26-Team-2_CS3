# app/services/dimension_scores_service.py

from uuid import UUID, uuid4
from datetime import datetime, timezone
from typing import List

from fastapi import HTTPException, status

from app.models.dimension import DimensionScoreCreate, DimensionScoreResponse
from app.services.snowflake import get_connection
from app.config import get_settings


def _fq_table(name: str) -> str:
    """Fully-qualified table name: DB.SCHEMA.TABLE"""
    s = get_settings()
    return f"{s.SNOWFLAKE_DATABASE}.{s.SNOWFLAKE_SCHEMA}.{name}"


TABLE = _fq_table("DIMENSION_SCORES")


def add_dimension_scores(assessment_id: UUID, scores: List[DimensionScoreCreate]) -> List[DimensionScoreResponse]:
    """
    Inserts multiple dimension score rows into Snowflake.
    Verifies rows exist immediately after insert.
    """
    insert_sql = f"""
        INSERT INTO {TABLE} (
            id, assessment_id, dimension, score, weight, confidence, evidence_count, created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """

    now = datetime.now(timezone.utc)
    created: List[DimensionScoreResponse] = []

    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # Debug: confirm session context
        cur.execute("SELECT CURRENT_DATABASE(), CURRENT_SCHEMA(), CURRENT_ROLE()")
        print("DIM_SCORES SESSION:", cur.fetchone())

        for s in scores:
            if s.assessment_id != assessment_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="assessment_id in body must match path parameter",
                )

            score_id = str(uuid4())

           
            weight = float(s.weight) if s.weight is not None else None
            confidence = float(s.confidence) if s.confidence is not None else None
            evidence_count = int(s.evidence_count) if s.evidence_count is not None else 0

            cur.execute(
                insert_sql,
                (
                    score_id,
                    str(assessment_id),
                    s.dimension.value,
                    float(s.score),
                    weight,
                    confidence,
                    evidence_count,
                    now,
                ),
            )

            created.append(
                DimensionScoreResponse(
                    id=UUID(score_id),
                    assessment_id=assessment_id,
                    dimension=s.dimension,
                    score=s.score,
                    weight=s.weight,
                    confidence=s.confidence,
                    evidence_count=s.evidence_count,
                    created_at=now,
                )
            )

        # ✅ Verify insert before commit (same transaction)
        cur.execute(
            f"SELECT COUNT(*) FROM {TABLE} WHERE assessment_id = %s",
            (str(assessment_id),)
        )
        cnt = cur.fetchone()[0]
        print("DIM_SCORES COUNT BEFORE COMMIT:", cnt)

        conn.commit()

        # ✅ Verify after commit too (still same connection)
        cur.execute(
            f"SELECT COUNT(*) FROM {TABLE} WHERE assessment_id = %s",
            (str(assessment_id),)
        )
        cnt2 = cur.fetchone()[0]
        print("DIM_SCORES COUNT AFTER COMMIT:", cnt2)

        # If still 0, something is definitely wrong -> don’t lie with “success”
        if cnt2 == 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Insert executed but no rows found after commit (check table name/schema/permissions)."
            )

        return created

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add dimension scores: {str(e)}",
        )
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def get_dimension_scores(assessment_id: UUID) -> List[DimensionScoreResponse]:
    select_sql = f"""
        SELECT id, assessment_id, dimension, score, weight, confidence, evidence_count, created_at
        FROM {TABLE}
        WHERE assessment_id = %s
        ORDER BY created_at DESC
    """

    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # Debug: confirm session context
        cur.execute("SELECT CURRENT_DATABASE(), CURRENT_SCHEMA(), CURRENT_ROLE()")
        print("DIM_SCORES SESSION:", cur.fetchone())

        cur.execute(select_sql, (str(assessment_id),))
        rows = cur.fetchall()

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch dimension scores: {str(e)}",
        )
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    return [
        DimensionScoreResponse(
            id=UUID(r[0]),
            assessment_id=UUID(r[1]),
            dimension=r[2],  # pydantic will coerce to enum if applicable
            score=float(r[3]),
            weight=float(r[4]) if r[4] is not None else None,
            confidence=float(r[5]) if r[5] is not None else None,
            evidence_count=int(r[6]) if r[6] is not None else 0,
            created_at=r[7],
        )
        for r in rows
    ]

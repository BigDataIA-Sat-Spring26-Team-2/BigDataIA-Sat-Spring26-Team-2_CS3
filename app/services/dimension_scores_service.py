# app/services/dimension_scores_service.py
from uuid import UUID, uuid4
from datetime import datetime, timezone
from typing import List

from fastapi import HTTPException, status

from app.models.dimension import DimensionScoreCreate, DimensionScoreResponse
from app.services import snowflake


def add_dimension_scores(assessment_id: UUID, scores: List[DimensionScoreCreate]) -> List[DimensionScoreResponse]:
    """
    Inserts multiple dimension score rows into Snowflake.
    Assumes dimension_scores table already exists.
    """
    conn = None
    cur = None
    created: List[DimensionScoreResponse] = []

    sql = """
        INSERT INTO dimension_scores (
            id, assessment_id, dimension, score, weight, confidence, evidence_count, created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """

    now = datetime.now(timezone.utc)

    try:
        conn = snowflake.get_connection()
        cur = conn.cursor()

        for s in scores:
            if s.assessment_id != assessment_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="assessment_id in body must match path parameter",
                )

            score_id = str(uuid4())

            # weight is already filled by your model validator if None
            cur.execute(
                sql,
                (
                    score_id,
                    str(assessment_id),
                    s.dimension.value,     # store as string
                    float(s.score),
                    float(s.weight),
                    float(s.confidence),
                    int(s.evidence_count),
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

        conn.commit()
        return created

    except HTTPException:
        raise
    except Exception as e:
        # If you have a UNIQUE(assessment_id, dimension), duplicates will come here
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
    sql = """
        SELECT id, assessment_id, dimension, score, weight, confidence, evidence_count, created_at
        FROM dimension_scores
        WHERE assessment_id = %s
        ORDER BY created_at DESC
    """

    conn = None
    cur = None
    try:
        conn = snowflake.get_connection()
        cur = conn.cursor()
        cur.execute(sql, (str(assessment_id),))
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

    results: List[DimensionScoreResponse] = []
    for r in rows:
        results.append(
            DimensionScoreResponse(
                id=UUID(r[0]),
                assessment_id=UUID(r[1]),
                dimension=r[2],  # pydantic will coerce into Dimension enum if your model uses it
                score=float(r[3]),
                weight=float(r[4]) if r[4] is not None else None,
                confidence=float(r[5]) if r[5] is not None else 0.8,
                evidence_count=int(r[6]) if r[6] is not None else 0,
                created_at=r[7],
            )
        )
    return results


def update_dimension_score(score_id: UUID, payload: DimensionScoreCreate) -> DimensionScoreResponse:
    now = datetime.now(timezone.utc)

    sql = """
        UPDATE dimension_scores
        SET score = %s,
            weight = %s,
            confidence = %s,
            evidence_count = %s
        WHERE id = %s
    """

    conn = None
    cur = None
    try:
        conn = snowflake.get_connection()
        cur = conn.cursor()
        cur.execute(
            sql,
            (
                float(payload.score),
                float(payload.weight),
                float(payload.confidence),
                int(payload.evidence_count),
                str(score_id),
            ),
        )

        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Score not found")

        conn.commit()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update dimension score: {str(e)}",
        )
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    # Return updated object (you can also re-select from DB, but this is fine)
    return DimensionScoreResponse(
        id=score_id,
        assessment_id=payload.assessment_id,
        dimension=payload.dimension,
        score=payload.score,
        weight=payload.weight,
        confidence=payload.confidence,
        evidence_count=payload.evidence_count,
        created_at=now,  # optional; if you want real created_at, reselect instead
    )

# app/services/dimension_scores_service.py

import math
from uuid import UUID, uuid4
from datetime import datetime, timezone
from typing import List
from app.services.redis_cache import cache
from app.models.enums import Dimension
from app.models.dimension import DimensionScoreCreate, DimensionScoreResponse, DIMENSION_WEIGHTS, DimensionWeightsResponse


from fastapi import HTTPException, status

from app.models.dimension import DimensionScoreCreate, DimensionScoreResponse
from app.services.snowflake import get_connection
from app.config import get_settings


def _fq_table(name: str) -> str:
    s = get_settings()
    return f"{s.SNOWFLAKE_DATABASE}.{s.SNOWFLAKE_SCHEMA}.{name}"


TABLE = _fq_table("DIMENSION_SCORES")


def add_dimension_scores(assessment_id: UUID, scores: List[DimensionScoreCreate]) -> List[DimensionScoreResponse]:
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
        cur.execute(
            "SELECT 1 FROM PE_ORGAIR.PUBLIC.ASSESSMENTS WHERE id = %s",
            (str(assessment_id),)
        )
        if not cur.fetchone():
            raise HTTPException(
                status_code=404,
                detail="Assessment not found"
            )

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

        conn.commit()
        return created

    except HTTPException:
        raise
    except Exception as e:
        msg = str(e).lower()
        if "unique" in msg or "duplicate" in msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A score for this assessment and dimension already exists"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add dimension scores"
        )
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# ✅ NEW: paginated list
def list_dimension_scores(
    assessment_id: UUID,
    page: int,
    page_size: int,
):
    """
    Paginated list of dimension scores for an assessment_id.
    Returns dict matching PaginatedResponse[DimensionScoreResponse].
    """
    offset = (page - 1) * page_size

    count_sql = f"""
        SELECT COUNT(*)
        FROM {TABLE}
        WHERE assessment_id = %s
    """

    data_sql = f"""
        SELECT id, assessment_id, dimension, score, weight, confidence, evidence_count, created_at
        FROM {TABLE}
        WHERE assessment_id = %s
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
    """

    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # total
        cur.execute(count_sql, (str(assessment_id),))
        total = cur.fetchone()[0]

        # page data
        cur.execute(data_sql, (str(assessment_id), page_size, offset))
        rows = cur.fetchall()

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list dimension scores: {str(e)}",
        )
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    items = [
        DimensionScoreResponse(
            id=UUID(r[0]),
            assessment_id=UUID(r[1]),
            dimension=r[2],  # pydantic will coerce to enum if needed
            score=float(r[3]),
            weight=float(r[4]) if r[4] is not None else None,
            confidence=float(r[5]) if r[5] is not None else None,
            evidence_count=int(r[6]) if r[6] is not None else 0,
            created_at=r[7],
        )
        for r in rows
    ]


    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


# (optional) keep old non-paginated getter for compatibility
def get_dimension_scores(assessment_id: UUID) -> List[DimensionScoreResponse]:
    return list_dimension_scores(assessment_id, page=1, page_size=100)["items"]

def get_dimension_weights() -> DimensionWeightsResponse:
    """
    Returns dimension weights.
    Cached for 24 hours as configuration data.
    """
    cache_key = "dimension:weights"

    # 1️⃣ Try Redis
    cached = cache.get(cache_key, DimensionWeightsResponse)
    if cached:
        return cached

    # 2️⃣ Source of truth (static config)
    weights_model = DimensionWeightsResponse(
        weights={d.value: w for d, w in DIMENSION_WEIGHTS.items()}
    )

    # 3️⃣ Store in Redis for 24 hours
    cache.set(cache_key, weights_model, ttl_seconds=60 * 60 * 24)

    return weights_model


def update_dimension_score(score_id: UUID, score: DimensionScoreCreate) -> DimensionScoreResponse:
    """Update an existing dimension score"""
    update_sql = f"""
        UPDATE {TABLE}
        SET score = %s,
            weight = %s,
            confidence = %s,
            evidence_count = %s
        WHERE id = %s
    """
    
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        # Verify score exists
        cur.execute(f"SELECT assessment_id, dimension FROM {TABLE} WHERE id = %s", (str(score_id),))
        existing = cur.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Dimension score not found")
        
        # Update
        cur.execute(
            update_sql,
            (
                float(score.score),
                float(score.weight) if score.weight is not None else None,
                float(score.confidence),
                int(score.evidence_count),
                str(score_id),
            ),
        )
        conn.commit()
        
        # Return updated score
        cur.execute(
            f"SELECT id, assessment_id, dimension, score, weight, confidence, evidence_count, created_at FROM {TABLE} WHERE id = %s",
            (str(score_id),)
        )
        row = cur.fetchone()
        
        return DimensionScoreResponse(
            id=UUID(row[0]),
            assessment_id=UUID(row[1]),
            dimension=row[2],
            score=float(row[3]),
            weight=float(row[4]) if row[4] else None,
            confidence=float(row[5]),
            evidence_count=int(row[6]),
            created_at=row[7],
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update dimension score: {str(e)}"
        )
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

from uuid import UUID, uuid4
from datetime import datetime, timezone
from typing import Optional
import math
from app.services.redis_cache import cache
 
from fastapi import HTTPException, status
 
from app.models.assessment import AssessmentCreate, AssessmentResponse
from app.models.enums import AssessmentStatus, AssessmentType
from app.services.snowflake import get_connection
 
 
def create_assessment(payload: AssessmentCreate) -> AssessmentResponse:
    assessment_id = str(uuid4())
    now = datetime.now(timezone.utc)
 
    sql = """
        INSERT INTO assessments (
            id,
            company_id,
            assessment_type,
            assessment_date,
            status,
            primary_assessor,
            secondary_assessor,
            v_r_score,
            confidence_lower,
            confidence_upper,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, NULL, NULL, NULL, %s)
    """
 
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            sql,
            (
                assessment_id,
                str(payload.company_id),
                payload.assessment_type.value,
                payload.assessment_date.date(),
                AssessmentStatus.DRAFT.value,
                payload.primary_assessor,
                payload.secondary_assessor,
                now,
            ),
        )
        conn.commit()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create assessment: {str(e)}",
        )
    finally:
        cur.close()
        conn.close()
 
    return AssessmentResponse(
        id=UUID(assessment_id),
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
 
 
# def get_assessment_with_scores(assessment_id: UUID):
#     assessment_sql = """
#         SELECT id, company_id, assessment_type, assessment_date,
#                primary_assessor, secondary_assessor, status,
#                v_r_score, confidence_lower, confidence_upper, created_at
#         FROM assessments
#         WHERE id = %s
#     """
 
#     scores_sql = """
#         SELECT dimension, score, weight, confidence, evidence_count, created_at
#         FROM dimension_scores
#         WHERE assessment_id = %s
#     """
 
#     try:
#         conn = get_connection()
#         cur = conn.cursor()
 
#         cur.execute(assessment_sql, (str(assessment_id),))
#         assessment = cur.fetchone()
 
#         if not assessment:
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 detail="Assessment not found",
#             )
 
#         cur.execute(scores_sql, (str(assessment_id),))
#         scores = cur.fetchall()
 
#     except HTTPException:
#         raise
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Failed to fetch assessment: {str(e)}",
#         )
#     finally:
#         cur.close()
#         conn.close()
 
#     assessment_response = AssessmentResponse(
#         id=UUID(assessment[0]),
#         company_id=UUID(assessment[1]),
#         assessment_type=AssessmentType(assessment[2]),
#         assessment_date=assessment[3],
#         primary_assessor=assessment[4],
#         secondary_assessor=assessment[5],
#         status=AssessmentStatus(assessment[6]),
#         v_r_score=assessment[7],
#         confidence_lower=assessment[8],
#         confidence_upper=assessment[9],
#         created_at=assessment[10],
#     )
 
#     score_items = [
#         {
#             "dimension": s[0],
#             "score": s[1],
#             "weight": s[2],
#             "confidence": s[3],
#             "evidence_count": s[4],
#             "created_at": s[5],
#         }
#         for s in scores
#     ]
#     cache_key = f"assessment:{assessment_id}"

#     cached = cache.get(cache_key)
#     if cached:
#         return cached
#     response = {
#     "assessment": assessment_response,
#     "scores": score_items,
#     }

#     cache.set(cache_key, response, ttl_seconds=120)

#     return response
 
def get_assessment_with_scores(assessment_id: UUID):
    cache_key = f"assessment:{assessment_id}"

    cached_assessment = cache.get(cache_key, AssessmentResponse)
    if cached_assessment:
        return {
            "assessment": cached_assessment,
            "scores": []  # scores always fetched live
        }

    assessment_sql = """
        SELECT id, company_id, assessment_type, assessment_date,
               primary_assessor, secondary_assessor, status,
               v_r_score, confidence_lower, confidence_upper, created_at
        FROM assessments
        WHERE id = %s
    """

    scores_sql = """
        SELECT dimension, score, weight, confidence, evidence_count, created_at
        FROM dimension_scores
        WHERE assessment_id = %s
    """

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(assessment_sql, (str(assessment_id),))
    assessment = cur.fetchone()

    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    cur.execute(scores_sql, (str(assessment_id),))
    scores = cur.fetchall()

    cur.close()
    conn.close()

    assessment_response = AssessmentResponse(
        id=UUID(assessment[0]),
        company_id=UUID(assessment[1]),
        assessment_type=AssessmentType(assessment[2]),
        assessment_date=assessment[3],
        primary_assessor=assessment[4],
        secondary_assessor=assessment[5],
        status=AssessmentStatus(assessment[6]),
        v_r_score=assessment[7],
        confidence_lower=assessment[8],
        confidence_upper=assessment[9],
        created_at=assessment[10],
    )

    score_items = [
        {
            "dimension": s[0],
            "score": s[1],
            "weight": s[2],
            "confidence": s[3],
            "evidence_count": s[4],
            "created_at": s[5],
        }
        for s in scores
    ]

    cache.set(cache_key, assessment_response, ttl_seconds=120)

    return {
        "assessment": assessment_response,
        "scores": score_items,
    }


def list_assessments(
    company_id: UUID,
    page: int,
    page_size: int,
    status: Optional[AssessmentStatus] = None,
    assessment_type: Optional[AssessmentType] = None,
):
    offset = (page - 1) * page_size
 
    base_where = "WHERE company_id = %s"
    params = [str(company_id)]
 
    if status:
        base_where += " AND status = %s"
        params.append(status.value)
 
    if assessment_type:
        base_where += " AND assessment_type = %s"
        params.append(assessment_type.value)
 
    count_sql = f"""
        SELECT COUNT(*)
        FROM assessments
        {base_where}
    """
 
    data_sql = f"""
        SELECT id, company_id, assessment_type, assessment_date,
               primary_assessor, secondary_assessor, status,
               v_r_score, confidence_lower, confidence_upper, created_at
        FROM assessments
        {base_where}
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
    """
 
    try:
        conn = get_connection()
        cur = conn.cursor()
 
        cur.execute(count_sql, tuple(params))
        total = cur.fetchone()[0]
 
        cur.execute(data_sql, tuple(params + [page_size, offset]))
        rows = cur.fetchall()
 
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list assessments: {str(e)}",
        )
    finally:
        cur.close()
        conn.close()
 
    items = [
        AssessmentResponse(
            id=UUID(r[0]),
            company_id=UUID(r[1]),
            assessment_type=AssessmentType(r[2]),
            assessment_date=r[3],
            primary_assessor=r[4],
            secondary_assessor=r[5],
            status=AssessmentStatus(r[6]),
            v_r_score=r[7],
            confidence_lower=r[8],
            confidence_upper=r[9],
            created_at=r[10],
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
 
def update_assessment_status(
    assessment_id: UUID,
    status_value: AssessmentStatus,
) -> AssessmentResponse:
    now = datetime.now(timezone.utc)
 
    sql = """
        UPDATE assessments
        SET status = %s
        WHERE id = %s
    """
 
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(sql, (status_value.value, str(assessment_id)))
 
        if cur.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assessment not found",
            )
 
        conn.commit()
 
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update assessment status: {str(e)}",
        )
    finally:
        cur.close()
        conn.close()
 
    cache.delete(f"assessment:{assessment_id}")

    return get_assessment_with_scores(assessment_id)["assessment"]
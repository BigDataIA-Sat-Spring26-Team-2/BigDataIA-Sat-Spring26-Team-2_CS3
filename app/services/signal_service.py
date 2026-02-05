from uuid import UUID, uuid4
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
import math
import json

from fastapi import HTTPException, status

from app.config import get_settings
from app.services.snowflake import get_connection
from app.models.signal import (
    ExternalSignal,
    CompanySignalSummary,
    SignalCategory,
    SignalSource,
)


def _fq_table(name: str) -> str:
    s = get_settings()
    return f"{s.SNOWFLAKE_DATABASE}.{s.SNOWFLAKE_SCHEMA}.{name}"


SIGNALS_TABLE = _fq_table("EXTERNAL_SIGNALS")
SUMMARIES_TABLE = _fq_table("COMPANY_SIGNAL_SUMMARIES")
COMPANIES_TABLE = _fq_table("COMPANIES")


# def store_signal(signal: ExternalSignal) -> ExternalSignal:
#     if signal.id is None:
#         signal.id = uuid4()
    

#     sql = f"""
# INSERT INTO {SIGNALS_TABLE} (
#     id,
#     company_id,
#     category,
#     source,
#     signal_date,
#     raw_value,
#     normalized_score,
#     confidence,
#     metadata,
#     created_at
# )
# SELECT
#     %s,
#     %s,
#     %s,
#     %s,
#     %s,
#     %s,
#     %s,
#     %s,
#     PARSE_JSON(%s),
#     %s
# """
    
#     conn = None
#     cur = None
#     try:
#         conn = get_connection()
#         cur = conn.cursor()
        
#         cur.execute(
#             f"SELECT 1 FROM {COMPANIES_TABLE} WHERE id = %s AND is_deleted = FALSE",
#             (str(signal.company_id),)
#         )
#         if not cur.fetchone():
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 detail="Company not found"
#             )
        
#         cur.execute(
#             sql,
#             (
#                 str(signal.id),
#                 str(signal.company_id),
#                 signal.category.value,
#                 signal.source.value,
#                 signal.signal_date.date(),
#                 signal.raw_value,
#                 float(signal.normalized_score),
#                 float(signal.confidence),
#                 json.dumps(signal.metadata or {}),
#                 signal.created_at,
#             )
#         )
#         conn.commit()
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Failed to store signal: {str(e)}"
#         )
#     finally:
#         if cur:
#             cur.close()
#         if conn:
#             conn.close()
    
#     return signal

def store_signal(signal: ExternalSignal) -> ExternalSignal:
    """Store external signal in database"""
    import structlog
    logger = structlog.get_logger()
    
    if signal.id is None:
        signal.id = uuid4()
    
    logger.info(
        "=== STORE SIGNAL START ===",
        signal_id=str(signal.id),
        company_id=str(signal.company_id),
        category=signal.category.value,
        source=signal.source.value,
        score=signal.normalized_score
    )
    
    # Pre-convert metadata to JSON string
    try:
        metadata_json = json.dumps(signal.metadata or {})
        logger.info("Metadata serialized", size=len(metadata_json))
    except Exception as e:
        logger.error("FAILED to serialize metadata", error=str(e))
        raise
    
    # ✅ Use SELECT with PARSE_JSON instead of VALUES
    sql = f"""
    INSERT INTO {SIGNALS_TABLE} (
        id,
        company_id,
        category,
        source,
        signal_date,
        raw_value,
        normalized_score,
        confidence,
        metadata,
        created_at
    )
    SELECT 
        %s, 
        %s, 
        %s, 
        %s, 
        %s, 
        %s, 
        %s, 
        %s, 
        PARSE_JSON(%s), 
        %s
    """
    
    conn = None
    cur = None
    try:
        logger.info("Getting Snowflake connection...")
        conn = get_connection()
        cur = conn.cursor()
        logger.info("Connection established")
        
        # Check company exists
        logger.info("Checking company exists...")
        cur.execute(
            f"SELECT 1 FROM {COMPANIES_TABLE} WHERE id = %s AND is_deleted = FALSE",
            (str(signal.company_id),)
        )
        if not cur.fetchone():
            logger.error("Company not found", company_id=str(signal.company_id))
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Company not found: {signal.company_id}"
            )
        logger.info("Company exists - OK")
        
        # Prepare params
        params = (
            str(signal.id),
            str(signal.company_id),
            signal.category.value,
            signal.source.value,
            signal.signal_date.date(),
            signal.raw_value,
            float(signal.normalized_score),
            float(signal.confidence),
            metadata_json,  # JSON string that will be parsed
            signal.created_at,
        )
        
        logger.info(
            "Executing INSERT",
            id=params[0][:8],
            company_id=params[1][:8],
            category=params[2],
            score=params[6]
        )
        
        # Execute insert
        cur.execute(sql, params)
        
        rowcount = cur.rowcount
        logger.info("Rows affected", rowcount=rowcount)
        
        # Commit
        conn.commit()
        logger.info("Transaction committed")
        
        # Verify insertion
        cur.execute(
            f"SELECT COUNT(*) FROM {SIGNALS_TABLE} WHERE id = %s",
            (str(signal.id),)
        )
        count = cur.fetchone()[0]
        logger.info("Verification count", count=count)
        
        if count == 0:
            logger.error("VERIFICATION FAILED - Row not found after commit!")
            raise Exception("Signal was not inserted (verification failed)")
        
        logger.info("=== STORE SIGNAL SUCCESS ===", signal_id=str(signal.id))
        
    except HTTPException:
        logger.error("HTTPException raised")
        if conn:
            conn.rollback()
        raise
    except Exception as e:
        logger.error(
            "=== STORE SIGNAL FAILED ===",
            error=str(e),
            error_type=type(e).__name__
        )
        if conn:
            conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store signal: {str(e)}"
        )
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
        logger.info("Database connection closed")
    
    return signal


def get_signals_for_company(
    company_id: UUID,
    category: Optional[SignalCategory] = None,
    page: int = 1,
    page_size: int = 20
) -> Dict[str, Any]:
    offset = (page - 1) * page_size
    
    base_where = "WHERE company_id = %s"
    params = [str(company_id)]
    
    if category:
        base_where += " AND category = %s"
        params.append(category.value)
    
    count_sql = f"SELECT COUNT(*) FROM {SIGNALS_TABLE} {base_where}"
    
    data_sql = f"""
        SELECT id, company_id, category, source, signal_date,
               raw_value, normalized_score, confidence, metadata, created_at
        FROM {SIGNALS_TABLE}
        {base_where}
        ORDER BY signal_date DESC, created_at DESC
        LIMIT %s OFFSET %s
    """
    
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute(count_sql, tuple(params))
        total = cur.fetchone()[0]
        
        # Get page data
        cur.execute(data_sql, tuple(params + [page_size, offset]))
        rows = cur.fetchall()
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch signals: {str(e)}"
        )
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
    
    items = []
    for r in rows:
        items.append(
            ExternalSignal(
                id=UUID(r[0]),
                company_id=UUID(r[1]),
                category=SignalCategory(r[2]),
                source=SignalSource(r[3]),
                signal_date=r[4],
                raw_value=r[5],
                normalized_score=float(r[6]),
                confidence=float(r[7]),
                metadata=json.loads(r[8]) if r[8] else {},
                created_at=r[9],
            )
        )
    
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


def update_signal_summary(company_id: UUID) -> CompanySignalSummary:
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        cur.execute(
            f"SELECT ticker FROM {COMPANIES_TABLE} WHERE id = %s AND is_deleted = FALSE",
            (str(company_id),)
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company not found"
            )
        ticker = row[0]
        
        cur.execute(
            f"""
            SELECT category, normalized_score, confidence
            FROM {SIGNALS_TABLE}
            WHERE company_id = %s
              AND (category, created_at) IN (
                  SELECT category, MAX(created_at)
                  FROM {SIGNALS_TABLE}
                  WHERE company_id = %s
                  GROUP BY category
              )
            """,
            (str(company_id), str(company_id))
        )
        scores_data = cur.fetchall()
        
        scores = {
            "technology_hiring": 0.0,
            "innovation_activity": 0.0,
            "digital_presence": 0.0,
            "leadership_signals": 0.0,
        }
        
        for category, score, confidence in scores_data:
            scores[category] = float(score)
        
        # Calculate composite score (weighted)
        composite = (
            0.30 * scores["technology_hiring"] +
            0.25 * scores["innovation_activity"] +
            0.25 * scores["digital_presence"] +
            0.20 * scores["leadership_signals"]
        )
        
        # Get signal count
        cur.execute(
            f"SELECT COUNT(*) FROM {SIGNALS_TABLE} WHERE company_id = %s",
            (str(company_id),)
        )
        signal_count = cur.fetchone()[0]
        
        now = datetime.now(timezone.utc)
        
        # Upsert summary
        cur.execute(
            f"""
            MERGE INTO {SUMMARIES_TABLE} t
            USING (SELECT %s as company_id) s
            ON t.company_id = s.company_id
            WHEN MATCHED THEN
                UPDATE SET
                    ticker = %s,
                    technology_hiring_score = %s,
                    innovation_activity_score = %s,
                    digital_presence_score = %s,
                    leadership_signals_score = %s,
                    composite_score = %s,
                    signal_count = %s,
                    last_updated = %s
            WHEN NOT MATCHED THEN
                INSERT (
                    company_id, ticker,
                    technology_hiring_score, innovation_activity_score,
                    digital_presence_score, leadership_signals_score,
                    composite_score, signal_count, last_updated
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """,
            (
                str(company_id), 
                ticker, 
                scores["technology_hiring"],
                scores["innovation_activity"],
                scores["digital_presence"],
                scores["leadership_signals"],
                composite,
                signal_count,
                now,
                str(company_id),
                ticker,
                scores["technology_hiring"],
                scores["innovation_activity"],
                scores["digital_presence"],
                scores["leadership_signals"],
                composite,
                signal_count,
                now,
            )
        )
        conn.commit()
        
        return CompanySignalSummary(
            company_id=company_id,
            ticker=ticker,
            technology_hiring_score=scores["technology_hiring"],
            innovation_activity_score=scores["innovation_activity"],
            digital_presence_score=scores["digital_presence"],
            leadership_signals_score=scores["leadership_signals"],
            composite_score=composite,
            signal_count=signal_count,
            last_updated=now,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update signal summary: {str(e)}"
        )
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def get_signal_summary(company_id: UUID) -> CompanySignalSummary:
    sql = f"""
        SELECT company_id, ticker,
               technology_hiring_score, innovation_activity_score,
               digital_presence_score, leadership_signals_score,
               composite_score, signal_count, last_updated
        FROM {SUMMARIES_TABLE}
        WHERE company_id = %s
    """
    
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(sql, (str(company_id),))
        row = cur.fetchone()
        
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Signal summary not found for this company"
            )
        
        return CompanySignalSummary(
            company_id=UUID(row[0]),
            ticker=row[1],
            technology_hiring_score=float(row[2]) if row[2] else 0.0,
            innovation_activity_score=float(row[3]) if row[3] else 0.0,
            digital_presence_score=float(row[4]) if row[4] else 0.0,
            leadership_signals_score=float(row[5]) if row[5] else 0.0,
            composite_score=float(row[6]) if row[6] else 0.0,
            signal_count=int(row[7]) if row[7] else 0,
            last_updated=row[8],
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get signal summary: {str(e)}"
        )
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
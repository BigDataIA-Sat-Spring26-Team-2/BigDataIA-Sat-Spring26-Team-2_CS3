from uuid import uuid4, UUID
from datetime import datetime, timezone
from typing import Optional
import math

from fastapi import HTTPException, status

from app.config import get_settings
from app.models.company import CompanyCreate, CompanyResponse
from app.services import snowflake
from app.services.redis_cache import RedisCache

cache = RedisCache()


def _fq_table(name: str) -> str:
    s = get_settings()
    return f"{s.SNOWFLAKE_DATABASE}.{s.SNOWFLAKE_SCHEMA}.{name}"


COMPANIES_TABLE = _fq_table("COMPANIES")
INDUSTRIES_TABLE = _fq_table("INDUSTRIES")


def _ensure_industry_exists(cur, industry_id: UUID) -> None:
    cur.execute(
        f"SELECT 1 FROM {INDUSTRIES_TABLE} WHERE id = %s",
        (str(industry_id),),
    )
    if not cur.fetchone():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Industry not found",
        )


def create_company(payload: CompanyCreate) -> CompanyResponse:
    company_id = str(uuid4())
    now = datetime.now(timezone.utc)

    sql = f"""
        INSERT INTO {COMPANIES_TABLE} (
            id, name, ticker, industry_id, position_factor,
            is_deleted, created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, FALSE, %s, %s)
    """

    conn = None
    cur = None
    try:
        conn = snowflake.get_connection()
        cur = conn.cursor()

        _ensure_industry_exists(cur, payload.industry_id)

        cur.execute(
            sql,
            (
                company_id,
                payload.name,
                payload.ticker,
                str(payload.industry_id),
                payload.position_factor,
                now,
                now,
            ),
        )
        conn.commit()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create company: {str(e)}",
        )
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    return CompanyResponse(
        id=UUID(company_id),
        name=payload.name,
        ticker=payload.ticker,
        industry_id=payload.industry_id,
        position_factor=payload.position_factor,
        created_at=now,
        updated_at=now,
    )


def get_company_by_id(company_id: UUID) -> CompanyResponse:
    cache_key = f"company:{company_id}"
    cached_company = cache.get(cache_key, CompanyResponse)
    if cached_company:
        return cached_company

    sql = f"""
        SELECT id, name, ticker, industry_id, position_factor,
               created_at, updated_at
        FROM {COMPANIES_TABLE}
        WHERE id = %s AND is_deleted = FALSE
    """

    conn = None
    cur = None
    try:
        conn = snowflake.get_connection()
        cur = conn.cursor()
        cur.execute(sql, (str(company_id),))
        row = cur.fetchone()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch company: {str(e)}",
        )
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )

    company = CompanyResponse(
        id=UUID(row[0]),
        name=row[1],
        ticker=row[2],
        industry_id=UUID(row[3]),
        position_factor=row[4],
        created_at=row[5],
        updated_at=row[6],
    )

    cache.set(cache_key, company, ttl_seconds=300)
    return company


def list_companies(
    page: int,
    page_size: int,
    industry_id: Optional[UUID] = None,
):
    offset = (page - 1) * page_size

    base_where = "WHERE is_deleted = FALSE"
    params = []

    if industry_id:
        base_where += " AND industry_id = %s"
        params.append(str(industry_id))

    count_sql = f"""
        SELECT COUNT(*)
        FROM {COMPANIES_TABLE}
        {base_where}
    """

    data_sql = f"""
        SELECT id, name, ticker, industry_id, position_factor,
               created_at, updated_at
        FROM {COMPANIES_TABLE}
        {base_where}
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
    """

    conn = None
    cur = None
    try:
        conn = snowflake.get_connection()
        cur = conn.cursor()

        cur.execute(count_sql, tuple(params))
        total = cur.fetchone()[0]

        cur.execute(data_sql, tuple(params + [page_size, offset]))
        rows = cur.fetchall()

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list companies: {str(e)}",
        )
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    items = [
        CompanyResponse(
            id=UUID(r[0]),
            name=r[1],
            ticker=r[2],
            industry_id=UUID(r[3]),
            position_factor=r[4],
            created_at=r[5],
            updated_at=r[6],
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


def update_company(company_id: UUID, payload: CompanyCreate) -> CompanyResponse:
    now = datetime.now(timezone.utc)

    sql = f"""
        UPDATE {COMPANIES_TABLE}
        SET name = %s,
            ticker = %s,
            industry_id = %s,
            position_factor = %s,
            updated_at = %s
        WHERE id = %s AND is_deleted = FALSE
    """

    conn = None
    cur = None
    try:
        conn = snowflake.get_connection()
        cur = conn.cursor()

        _ensure_industry_exists(cur, payload.industry_id)

        cur.execute(
            sql,
            (
                payload.name,
                payload.ticker,
                str(payload.industry_id),
                payload.position_factor,
                now,
                str(company_id),
            ),
        )
        if cur.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company not found",
            )
        conn.commit()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update company: {str(e)}",
        )
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    cache.delete(f"company:{company_id}")
    return get_company_by_id(company_id)


def delete_company(company_id: UUID) -> None:
    sql = f"""
        UPDATE {COMPANIES_TABLE}
        SET is_deleted = TRUE,
            updated_at = %s
        WHERE id = %s AND is_deleted = FALSE
    """

    conn = None
    cur = None
    try:
        conn = snowflake.get_connection()
        cur = conn.cursor()
        cur.execute(sql, (datetime.now(timezone.utc), str(company_id)))
        if cur.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company not found",
            )
        conn.commit()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete company: {str(e)}",
        )
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    cache.delete(f"company:{company_id}")


def hard_delete_company(company_id: UUID) -> None:
    sql = f"DELETE FROM {COMPANIES_TABLE} WHERE id = %s"

    conn = None
    cur = None
    try:
        conn = snowflake.get_connection()
        cur = conn.cursor()
        cur.execute(sql, (str(company_id),))
        conn.commit()

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to hard delete company: {str(e)}",
        )
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    cache.delete(f"company:{company_id}")

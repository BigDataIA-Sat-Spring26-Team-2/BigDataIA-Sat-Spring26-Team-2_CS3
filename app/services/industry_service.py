from uuid import UUID, uuid4
from datetime import datetime, timezone
from typing import Optional
import math
from fastapi import HTTPException, status
from app.models.industry import IndustryCreate, IndustryResponse
from app.models.enums import Sector
from app.services.snowflake import get_connection


def create_industry(payload: IndustryCreate) -> IndustryResponse:
    industry_id = str(uuid4())
    now = datetime.now(timezone.utc)

    sql = """
        INSERT INTO industries (
            id, name, sector, h_r_base, created_at
        )
        VALUES (%s, %s, %s, %s, %s)
    """

    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            sql,
            (
                industry_id,
                payload.name,
                payload.sector.value,
                payload.h_r_base,
                now,
            ),
        )
        conn.commit()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create industry: {str(e)}",
        )
    finally:
        cur.close()
        conn.close()

    return IndustryResponse(
        id=UUID(industry_id),
        name=payload.name,
        sector=payload.sector,
        h_r_base=payload.h_r_base,
        created_at=now,
    )


def get_industry_by_id(industry_id: UUID) -> IndustryResponse:
    sql = """
        SELECT id, name, sector, h_r_base, created_at
        FROM industries
        WHERE id = %s
    """

    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(sql, (str(industry_id),))
        row = cur.fetchone()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch industry: {str(e)}",
        )
    finally:
        cur.close()
        conn.close()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Industry not found",
        )

    return IndustryResponse(
        id=UUID(row[0]),
        name=row[1],
        sector=Sector(row[2]),
        h_r_base=row[3],
        created_at=row[4],
    )


def list_industries(
    page: int,
    page_size: int,
    sector: Optional[Sector] = None,
    name_contains: Optional[str] = None,
):
    offset = (page - 1) * page_size

    base_where = "WHERE 1=1"
    params = []

    if sector:
        base_where += " AND sector = %s"
        params.append(sector.value)

    if name_contains:
        base_where += " AND LOWER(name) LIKE %s"
        params.append(f"%{name_contains.lower()}%")

    count_sql = f"""
        SELECT COUNT(*)
        FROM industries
        {base_where}
    """

    data_sql = f"""
        SELECT id, name, sector, h_r_base, created_at
        FROM industries
        {base_where}
        ORDER BY name
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
            detail=f"Failed to list industries: {str(e)}",
        )
    finally:
        cur.close()
        conn.close()

    items = [
        IndustryResponse(
            id=UUID(r[0]),
            name=r[1],
            sector=Sector(r[2]),
            h_r_base=r[3],
            created_at=r[4],
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

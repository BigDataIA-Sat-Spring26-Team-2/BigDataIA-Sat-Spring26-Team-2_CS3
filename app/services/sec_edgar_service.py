from typing import List, Optional
from uuid import UUID, uuid4
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException

from app.pipelines.sec_edgar import SECEdgarPipeline
from app.pipelines.document_parser import DocumentParser
from app.pipelines.chunker import chunk_text
from app.services.snowflake import get_connection
from app.config import get_settings


def _fq(name: str) -> str:
    s = get_settings()
    return f"{s.SNOWFLAKE_DATABASE}.{s.SNOWFLAKE_SCHEMA}.{name}"


DOCS_TABLE = _fq("DOCUMENTS")
CHUNKS_TABLE = _fq("DOCUMENT_CHUNKS")   # use your real table name
COMPANIES_TABLE = _fq("COMPANIES")


def run_sec_download_for_company(
    company_id: UUID,
    ticker: Optional[str],
    cik: Optional[str],
    filing_types: List[str],
    limit: int,
    after: str,
) -> dict:
    settings = get_settings()

    pipeline = SECEdgarPipeline(
        company_name="PE OrgAIR Platform",
        email="you@example.com",   # put real email or read from env
        download_dir=Path("data/raw/sec"),
    )
    parser = DocumentParser()

    # FK validation: company exists
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            f"SELECT ticker FROM {COMPANIES_TABLE} WHERE id=%s AND is_deleted=FALSE",
            (str(company_id),),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Company not found")

        db_ticker = row[0]  # could be None
    finally:
        if cur: cur.close()
        if conn: conn.close()

    # If ticker not provided, fall back to DB ticker (if present)
    if not ticker and db_ticker:
        ticker = db_ticker.upper()

    # Still no ticker and no cik -> error (extra safety)
    if not ticker and not cik:
        raise HTTPException(status_code=400, detail="No ticker found for this company and cik not provided")

    # Download by cik OR ticker
    downloaded = pipeline.download_filings(
        ticker=ticker,
        cik=cik,
        filing_types=filing_types,
        limit=limit,
        after=after,
    )

    inserted_docs = 0
    inserted_chunks = 0
    skipped_duplicates = 0

    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        for f in downloaded:
            file_path = Path(f.path)
            parsed = parser.parse_filing(file_path, ticker=(ticker or ""), filing_type=f.filing_type)

            # dedupe
            cur.execute(f"SELECT 1 FROM {DOCS_TABLE} WHERE content_hash=%s", (parsed.content_hash,))
            if cur.fetchone():
                skipped_duplicates += 1
                continue

            doc_id = str(uuid4())
            now = datetime.now(timezone.utc)

            cur.execute(
                f"""
                INSERT INTO {DOCS_TABLE} (
                    id, company_id, cik, ticker, filing_type, accession_number,
                    source, source_url, file_path,
                    filing_date, content_hash, word_count, created_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    doc_id,
                    str(company_id),
                    cik,
                    ticker,
                    f.filing_type,
                    f.accession_number,
                    "sec_edgar",
                    None,
                    parsed.source_path,
                    parsed.filing_date.date(),
                    parsed.content_hash,
                    parsed.word_count,
                    now,
                ),
            )
            inserted_docs += 1

            chunks = chunk_text(parsed.content, chunk_size_words=350, overlap_words=50)
            for c in chunks:
                chunk_id = str(uuid4())
                cur.execute(
                    f"""
                    INSERT INTO {CHUNKS_TABLE} (
                        id, document_id, chunk_index, chunk_text, content_hash, word_count, created_at
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        chunk_id,
                        doc_id,
                        c.chunk_index,
                        c.text,
                        c.content_hash,
                        c.word_count,
                        now,
                    ),
                )
                inserted_chunks += 1

        conn.commit()

    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=f"SEC pipeline failed: {str(e)}")
    finally:
        if cur: cur.close()
        if conn: conn.close()

    return {
        "company_id": str(company_id),
        "ticker": ticker,
        "cik": cik,
        "downloaded_files": len(downloaded),
        "inserted_documents": inserted_docs,
        "inserted_chunks": inserted_chunks,
        "skipped_duplicates": skipped_duplicates,
        "after": after,
        "limit": limit,
        "filing_types": filing_types,
    }

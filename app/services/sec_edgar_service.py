# app/services/sec_edgar_service.py
from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timezone

from fastapi import HTTPException, status

from app.config import get_settings
from app.services.snowflake import get_connection
from app.pipelines.sec_edgar import SECEdgarPipeline
from app.pipelines.document_parser import DocumentParser
from app.pipelines.chunker import chunk_text

from app.pipelines.sec_edgar import SECEdgarPipeline

def _fq(name: str) -> str:
    s = get_settings()
    return f"{s.SNOWFLAKE_DATABASE}.{s.SNOWFLAKE_SCHEMA}.{name}"


COMPANIES_TABLE = _fq("COMPANIES")
DOCS_TABLE = _fq("DOCUMENTS")
CHUNKS_TABLE = _fq("DOCUMENT_CHUNKS")


def _sec_pipeline() -> SECEdgarPipeline:
    """
    Central place to configure SEC downloader identity + output dir.
    Change via env later if needed.
    """
    s = get_settings()

    company_name = getattr(s, "SEC_DOWNLOADER_COMPANY", None) or "PE OrgAIR Team-2"
    email = getattr(s, "SEC_DOWNLOADER_EMAIL", None) or "you@example.com"
    download_dir = Path(getattr(s, "SEC_DOWNLOAD_DIR", None) or "data/raw/sec")

    download_dir.mkdir(parents=True, exist_ok=True)

    return SECEdgarPipeline(
        company_name=company_name,
        email=email,
        download_dir=download_dir,
    )


def download_by_cik(
    cik: str,
    filing_types: List[str],
    after: str,
    limit: int,
) -> Dict[str, Any]:
    """
    Simple helper if you want a pure CIK download (no DB inserts).
    Keeps things predictable while you build out storage features.
    """
    pipeline = _sec_pipeline()

    # use the pipeline's generic downloader (CIK path)
    filings = pipeline.download_filings(
        ticker=None,
        cik=str(cik),
        filing_types=filing_types,
        limit=limit,
        after=after,
    )

    files = [{"filing_type": f.filing_type, "accession_number": f.accession_number, "path": f.path} for f in filings]

    return {
        "cik": cik,
        "downloaded_files": len(filings),
        "after": after,
        "limit": limit,
        "filing_types": filing_types,
        "files": files,
    }


def run_sec_download_for_company(
    company_id: UUID,
    ticker: Optional[str],
    cik: Optional[str],
    filing_types: List[str],
    limit: int,
    after: str,
) -> Dict[str, Any]:
    """
    End-to-end pipeline:
      1) Validate company exists
      2) Download SEC filings (ticker or CIK)
      3) Parse, hash, dedupe
      4) Insert DOCUMENTS
      5) Chunk + insert DOCUMENT_CHUNKS
      6) Return summary + list of downloaded file paths
    """

    # ---------- validate inputs ----------
    if not ticker and not cik:
        raise HTTPException(status_code=400, detail="Provide either ticker or cik")

    if ticker:
        ticker = ticker.upper()

    # ---------- validate company exists + maybe get ticker from DB ----------
    conn = None
    cur = None
    db_ticker: Optional[str] = None
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
        db_ticker = row[0] if row else None
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    # If ticker not supplied but exists in DB, use it
    if not ticker and db_ticker:
        ticker = str(db_ticker).upper()

    # Still no identifier?
    if not ticker and not cik:
        raise HTTPException(
            status_code=400,
            detail="No ticker found for this company and cik not provided",
        )

    # ---------- run download ----------
    pipeline = _sec_pipeline()
    parser = DocumentParser()

    downloaded = pipeline.download_filings(
        ticker=ticker,
        cik=cik,
        filing_types=filing_types,
        limit=limit,
        after=after,
    )

    # ---------- insert into Snowflake ----------
    inserted_docs = 0
    inserted_chunks = 0
    skipped_duplicates = 0

    files = [{"filing_type": f.filing_type, "accession_number": f.accession_number, "path": f.path} for f in downloaded]

    if not downloaded:
        return {
            "company_id": str(company_id),
            "ticker": ticker,
            "cik": cik,
            "downloaded_files": 0,
            "inserted_documents": 0,
            "inserted_chunks": 0,
            "skipped_duplicates": 0,
            "after": after,
            "limit": limit,
            "filing_types": filing_types,
            "files": [],
        }

    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        for f in downloaded:
            file_path = Path(f.path)

            parsed = parser.parse_filing(
                file_path=file_path,
                ticker=(ticker or ""),
                filing_type=f.filing_type,
            )

            # dedupe by content hash
            cur.execute(f"SELECT 1 FROM {DOCS_TABLE} WHERE content_hash=%s", (parsed.content_hash,))
            if cur.fetchone():
                skipped_duplicates += 1
                continue

            doc_id = str(uuid4())
            now = datetime.now(timezone.utc)

            # Insert document metadata
            cur.execute(
                f"""
                INSERT INTO {DOCS_TABLE} (
                    id, company_id, cik, ticker, filing_type, accession_number,
                    file_path, filing_date, content_hash, word_count, created_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    doc_id,
                    str(company_id),
                    cik,
                    ticker,
                    f.filing_type,
                    f.accession_number,
                    parsed.source_path,
                    parsed.filing_date.date(),
                    parsed.content_hash,
                    parsed.word_count,
                    now,
                ),
            )
            inserted_docs += 1

            # Chunk + insert chunks
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
            try:
                conn.rollback()
            except Exception:
                pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SEC pipeline failed: {str(e)}",
        )
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

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
        "files": files,
    }

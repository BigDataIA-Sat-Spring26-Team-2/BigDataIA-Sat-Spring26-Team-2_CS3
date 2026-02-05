# app/services/sec_edgar_service.py
from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timezone, date
import hashlib

from fastapi import HTTPException

from app.config import get_settings
from app.services.snowflake import get_connection
from app.pipelines.sec_edgar import SECEdgarPipeline
from app.pipelines.document_parser import DocumentParser
from app.services.s3_storage import upload_file_to_s3, s3_object_exists
import structlog

logger = structlog.get_logger()


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


def _after_to_date(after: str) -> date:
    # Streamlit passes YYYY-MM-DD
    return datetime.fromisoformat(after).date()


def _s3_key_for_filing(ticker: str, filing_type: str, accession_number: str) -> str:
    # MUST match your upload key exactly
    return f"sec/{ticker}/{filing_type}/{accession_number}/full-submission.txt"


def download_by_cik(
    cik: str,
    filing_types: List[str],
    after: str,
    limit: int,
) -> Dict[str, Any]:
    pipeline = _sec_pipeline()

    filings = pipeline.download_filings(
        ticker=None,
        cik=str(cik),
        filing_types=filing_types,
        limit=limit,
        after=after,
    )

    files = [
        {"filing_type": f.filing_type, "accession_number": f.accession_number, "path": f.path}
        for f in filings
    ]

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

    logger.info(
        "sec_pipeline_started",
        company_id=str(company_id),
        ticker=ticker,
        cik=cik,
        filing_types=filing_types,
        limit=limit,
        after=after,
    )

    if not ticker and not cik:
        raise HTTPException(status_code=400, detail="Provide either ticker or cik")

    if ticker:
        ticker = ticker.upper()

    # -------------------------
    # Resolve ticker from DB if not provided
    # -------------------------
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
        db_ticker = row[0]
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    if not ticker and db_ticker:
        ticker = str(db_ticker).upper()

    # Your S3 key format is sec/{ticker}/..., so ticker must exist
    if not ticker:
        raise HTTPException(
            status_code=400,
            detail="Ticker is required (provide ticker or ensure company has ticker).",
        )

    settings = get_settings()
    after_dt = _after_to_date(after)

    # ============================================================
    # 1) CACHE PHASE: Snowflake (index) -> S3 head_object (confirm)
    # ============================================================
    cached_files: List[Dict[str, Any]] = []
    cache_hits_by_type: Dict[str, int] = {ft: 0 for ft in filing_types}

    conn = get_connection()
    cur = conn.cursor()
    try:
        for ft in filing_types:
            cur.execute(
                f"""
                SELECT accession_number, filing_date
                FROM {DOCS_TABLE}
                WHERE company_id=%s
                  AND ticker=%s
                  AND filing_type=%s
                  AND filing_date >= %s
                ORDER BY filing_date DESC
                LIMIT %s
                """,
                (str(company_id), ticker, ft, after_dt, limit),
            )
            rows = cur.fetchall() or []

            for accession_number, filing_date in rows:
                s3_key = _s3_key_for_filing(ticker, ft, accession_number)

                if s3_object_exists(settings.S3_BUCKET, s3_key):
                    cached_files.append(
                        {
                            "filing_type": ft,
                            "accession_number": accession_number,
                            "path": f"s3://{settings.S3_BUCKET}/{s3_key}",
                            "source": "s3_cache",
                            "filing_date": str(filing_date),
                        }
                    )
                    cache_hits_by_type[ft] += 1

    finally:
        cur.close()
        conn.close()

    # Full cache hit: enough cached filings for each filing type
    if all(cache_hits_by_type.get(ft, 0) >= limit for ft in filing_types):
        logger.info(
            "sec_cache_hit_full",
            ticker=ticker,
            after=after,
            limit_per_type=limit,
            cache_hits_by_type=cache_hits_by_type,
        )
        return {
            "company_id": str(company_id),
            "ticker": ticker,
            "cik": cik,
            "cache_hits": sum(cache_hits_by_type.values()),
            "cache_hits_by_type": cache_hits_by_type,
            "downloaded_files": 0,
            "inserted_documents": 0,
            "inserted_chunks": 0,
            "skipped_duplicates": 0,
            "after": after,
            "limit": limit,
            "filing_types": filing_types,
            "files": cached_files,
        }

    # ============================================================
    # 2) MISS PHASE: Download only what’s missing per filing type
    # ============================================================
    logger.info(
        "sec_cache_partial_or_miss",
        ticker=ticker,
        cache_hits_by_type=cache_hits_by_type,
        limit_per_type=limit,
    )

    pipeline = _sec_pipeline()
    parser = DocumentParser()

    downloaded_all = []
    for ft in filing_types:
        remaining = max(0, limit - cache_hits_by_type.get(ft, 0))
        if remaining == 0:
            continue

        newly_downloaded = pipeline.download_filings(
            ticker=ticker,
            cik=cik,
            filing_types=[ft],
            limit=remaining,
            after=after,
        )
        downloaded_all.extend(newly_downloaded)

    inserted_docs = 0
    inserted_chunks = 0
    skipped_duplicates = 0

    new_files = [
        {"filing_type": f.filing_type, "accession_number": f.accession_number, "path": f.path}
        for f in downloaded_all
    ]

    conn = get_connection()
    cur = conn.cursor()

    try:
        for f in downloaded_all:
            file_path = Path(f.path)

            parsed = parser.parse_filing(file_path=file_path, ticker=ticker or "")

            # Duplicate check by content hash (your existing approach)
            cur.execute(f"SELECT 1 FROM {DOCS_TABLE} WHERE content_hash=%s", (parsed.content_hash,))
            if cur.fetchone():
                skipped_duplicates += 1
                try:
                    file_path.unlink()
                except Exception:
                    pass
                continue

            # Upload to S3
            s3_key = _s3_key_for_filing(ticker, f.filing_type, f.accession_number)
            upload_file_to_s3(file_path, s3_key)
            file_path.unlink()

            # SECTION-LEVEL DEDUP + CHUNKING WITH LOGGING
            # SECTION-LEVEL DEDUP + CHUNKING WITH LOGGING
            sections_extracted = len(parsed.sections)
            sections_stored = 0
            sections_duplicates = 0
            section_data = []

            chunk_index = 0
            
            # Log what sections were extracted
            logger.info(
                "sections_extracted",
                ticker=ticker,
                filing_type=f.filing_type,
                sections_found=list(parsed.sections.keys()),
                section_count=sections_extracted
            )

            # SINGLE LOOP - processes all sections
            for section_name, section_content in parsed.sections.items():
                # ✅ FILTER: Skip invalid section/filing combinations
                if section_name == 'executive_compensation' and f.filing_type == '10-K':
                    logger.warning(
                        "skipping_invalid_section",
                        ticker=ticker,
                        filing_type=f.filing_type,
                        section=section_name,
                        reason="10-K should not have compensation section (likely TOC match)"
                    )
                    continue
                
                words = section_content.split()
                section_word_count = len(words)
                
                # Log section details
                logger.info(
                    "processing_section",
                    ticker=ticker,
                    filing_type=f.filing_type,
                    section=section_name,
                    word_count=section_word_count,
                    will_chunk=(section_word_count >= 5000)
                )

                # Chunking decision
                if len(words) < 5000:
                    chunks = [(chunk_index, section_content)]
                    next_index = chunk_index + 1
                    
                    logger.debug(
                        "section_stored_whole",
                        section=section_name,
                        word_count=section_word_count,
                        chunk_index=chunk_index
                    )
                else:
                    chunks = []
                    start = 0
                    idx_c = chunk_index
                    
                    while start < len(words):
                        end = min(start + 1000, len(words))
                        chunks.append((idx_c, " ".join(words[start:end])))
                        idx_c += 1
                        if end == len(words):
                            break
                        start = end - 100
                    
                    next_index = idx_c
                    
                    logger.info(
                        "section_chunked",
                        section=section_name,
                        total_words=section_word_count,
                        chunks_created=len(chunks),
                        avg_chunk_size=section_word_count // len(chunks) if len(chunks) > 0 else 0
                    )

                # Process chunks
                chunks_added_this_section = 0
                chunks_skipped_this_section = 0
                
                for idx_c, chunk_text in chunks:
                    chunk_hash = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
                    chunk_word_count = len(chunk_text.split())

                    cur.execute(f"SELECT 1 FROM {CHUNKS_TABLE} WHERE content_hash=%s", (chunk_hash,))
                    if cur.fetchone():
                        sections_duplicates += 1
                        chunks_skipped_this_section += 1
                        continue

                    section_data.append(
                        (str(uuid4()), None, idx_c, chunk_text, chunk_hash, chunk_word_count, section_name, None)
                    )
                    sections_stored += 1
                    chunks_added_this_section += 1

                logger.info(
                    "section_processed",
                    section=section_name,
                    chunks_added=chunks_added_this_section,
                    chunks_skipped=chunks_skipped_this_section,
                    total_section_chunks=len(chunks)
                )

                chunk_index = next_index

            # Summary log
            logger.info(
                "chunking_complete",
                ticker=ticker,
                filing_type=f.filing_type,
                sections_extracted=sections_extracted,
                sections_stored=sections_stored,
                sections_duplicates=sections_duplicates,
                total_chunks_to_insert=len(section_data)
            )

            # INSERT DOCUMENT
            doc_id = str(uuid4())
            now = datetime.now(timezone.utc)

            cur.execute(
                f"""
                INSERT INTO {DOCS_TABLE} (
                    id, company_id, cik, ticker, filing_type, accession_number,
                    file_path, filing_date, content_hash, word_count,
                    sections_extracted, sections_stored, sections_duplicates,
                    created_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
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
                    sections_extracted,
                    sections_stored,
                    sections_duplicates,
                    now,
                ),
            )

            inserted_docs += 1

            if section_data:
                final_sections = []
                for sid, _, idx_c, txt, h, wc, section_name, _ in section_data:
                    final_sections.append(
                        (sid, doc_id, idx_c, txt, h, wc, section_name, now)
                    )
                
                cur.executemany(
                    f"""
                    INSERT INTO {CHUNKS_TABLE} (
                        id, document_id, chunk_index, chunk_text,
                        content_hash, word_count, section, created_at
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    final_sections,
                )
                inserted_chunks += len(final_sections)
                
                # ✅ ADD: Log successful insert
                logger.info(
                    "chunks_inserted",
                    ticker=ticker,
                    filing_type=f.filing_type,
                    chunks_inserted=len(final_sections)
                )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()

    combined_files = cached_files + [
        {
            "filing_type": f.get("filing_type"),
            "accession_number": f.get("accession_number"),
            "path": f.get("path"),
            "source": "downloaded",
        }
        for f in new_files
    ]

    return {
        "company_id": str(company_id),
        "ticker": ticker,
        "cik": cik,
        "cache_hits": sum(cache_hits_by_type.values()),
        "cache_hits_by_type": cache_hits_by_type,
        "downloaded_files": len(downloaded_all),
        "inserted_documents": inserted_docs,
        "inserted_chunks": inserted_chunks,
        "skipped_duplicates": skipped_duplicates,
        "after": after,
        "limit": limit,
        "filing_types": filing_types,
        "files": combined_files,
    }